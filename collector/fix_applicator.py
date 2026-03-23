"""
Programmatic Fix Application for Fabric Data Agents.

Reads the current agent definition via the Fabric REST API, applies
remediation artifacts (optimized instructions, verified answers, schema
scope), and writes the updated definition back.

All mutations are gated behind a dry_run flag so the caller can preview
changes before committing them.
"""

import base64
import json
import sys
import time

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
MAX_INSTRUCTION_CHARS = 3800  # Leave headroom below Fabric's 4000 limit


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _poll_lro(op_url, headers, max_wait=300, interval=3):
    """Poll a Fabric long-running operation until terminal state."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = requests.get(op_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            body = resp.json()
            status = body.get("status", "").lower()
            if status in ("succeeded", "completed"):
                return {"status": "succeeded", "body": body}
            if status in ("failed", "cancelled"):
                return {"status": status, "error": body.get("error", str(body))}
        elif resp.status_code == 202:
            pass  # still running
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
        time.sleep(interval)
    return {"status": "timeout", "error": f"LRO timed out after {max_wait}s"}


# ── Read / Write Agent Definition ──────────────────────────────────

def get_agent_definition(workspace_id, artifact_id, token):
    """Fetch and decode the agent definition parts."""
    url = f"{FABRIC_BASE}/workspaces/{workspace_id}/dataAgents/{artifact_id}/getDefinition"
    resp = requests.post(url, headers=_headers(token), timeout=30)

    # Handle LRO (202 with Operation-Location header)
    if resp.status_code == 202:
        op_url = resp.headers.get("Operation-Location") or resp.headers.get("Location")
        if op_url:
            lro = _poll_lro(op_url, _headers(token))
            if lro["status"] != "succeeded":
                return {"error": f"LRO failed: {lro.get('error', 'unknown')}"}
            # Re-fetch definition after LRO completes
            resp = requests.post(url, headers=_headers(token), timeout=30)

    if resp.status_code not in (200, 201):
        return {"error": f"getDefinition returned {resp.status_code}: {resp.text[:500]}"}

    raw_parts = resp.json().get("definition", {}).get("parts", [])
    decoded = {}
    for part in raw_parts:
        path = part.get("path", "")
        payload = part.get("payload", "")
        try:
            decoded[path] = json.loads(base64.b64decode(payload).decode("utf-8"))
        except Exception:
            decoded[path] = payload  # keep raw if not JSON
    return {"parts": decoded, "raw_parts": raw_parts}


def update_agent_definition(workspace_id, artifact_id, token, definition_parts):
    """Encode and write the full agent definition back to Fabric."""
    encoded_parts = []
    for path, content in definition_parts.items():
        if isinstance(content, (dict, list)):
            payload = base64.b64encode(json.dumps(content).encode("utf-8")).decode("utf-8")
        else:
            payload = base64.b64encode(str(content).encode("utf-8")).decode("utf-8")
        encoded_parts.append({"path": path, "payload": payload})

    url = f"{FABRIC_BASE}/workspaces/{workspace_id}/dataAgents/{artifact_id}/updateDefinition"
    body = {"definition": {"parts": encoded_parts}}
    resp = requests.post(url, headers=_headers(token), json=body, timeout=60)

    if resp.status_code == 202:
        op_url = resp.headers.get("Operation-Location") or resp.headers.get("Location")
        if op_url:
            return _poll_lro(op_url, _headers(token))
        return {"status": "accepted", "note": "202 with no LRO URL"}

    if resp.status_code in (200, 201):
        return {"status": "succeeded"}

    return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}


# ── Individual Fix Functions ───────────────────────────────────────

def apply_optimized_instructions(workspace_id, artifact_id, token, new_instructions):
    """Replace the agent's AI instructions with optimized text."""
    defn = get_agent_definition(workspace_id, artifact_id, token)
    if "error" in defn:
        return defn

    # Truncate if needed
    if len(new_instructions) > MAX_INSTRUCTION_CHARS:
        new_instructions = new_instructions[:MAX_INSTRUCTION_CHARS]
        print(f"[fix] Instructions truncated to {MAX_INSTRUCTION_CHARS} chars", file=sys.stderr)

    parts = defn["parts"]
    updated = False
    for path, content in parts.items():
        if isinstance(content, dict):
            # Look for instructions field in agent config
            if "instructions" in content:
                old_len = len(content.get("instructions", ""))
                content["instructions"] = new_instructions
                updated = True
                print(f"[fix] Updated instructions in {path}: {old_len} -> {len(new_instructions)} chars",
                      file=sys.stderr)
            # Also check nested aiConfig
            if "aiConfig" in content and isinstance(content["aiConfig"], dict):
                if "instructions" in content["aiConfig"]:
                    content["aiConfig"]["instructions"] = new_instructions
                    updated = True

    if not updated:
        return {"error": "Could not find instructions field in agent definition"}

    return update_agent_definition(workspace_id, artifact_id, token, parts)


def apply_verified_answers(workspace_id, artifact_id, token, verified_answers):
    """Add verified answer patterns to the agent definition (no duplicates)."""
    defn = get_agent_definition(workspace_id, artifact_id, token)
    if "error" in defn:
        return defn

    parts = defn["parts"]
    added = 0
    for path, content in parts.items():
        if isinstance(content, dict):
            vas = content.get("verifiedAnswers", content.get("verified_answers", []))
            if isinstance(vas, list):
                existing_qs = {va.get("question", "").strip().lower() for va in vas}
                for va in verified_answers:
                    q = va.get("question", "").strip()
                    if q.lower() not in existing_qs:
                        vas.append(va)
                        existing_qs.add(q.lower())
                        added += 1
                # Write back
                if "verifiedAnswers" in content:
                    content["verifiedAnswers"] = vas
                else:
                    content["verified_answers"] = vas

    if added == 0:
        return {"status": "no_change", "message": "No new verified answers to add (all duplicates or no VA field)"}

    print(f"[fix] Added {added} new verified answers", file=sys.stderr)
    return update_agent_definition(workspace_id, artifact_id, token, parts)


def apply_schema_scope(workspace_id, artifact_id, token, include_tables=None, exclude_tables=None):
    """Update the agent's schema scope (include/exclude tables)."""
    defn = get_agent_definition(workspace_id, artifact_id, token)
    if "error" in defn:
        return defn

    parts = defn["parts"]
    updated = False
    for path, content in parts.items():
        if isinstance(content, dict):
            for ds in content.get("dataSources", []):
                if include_tables is not None:
                    ds["includeTables"] = include_tables
                    updated = True
                if exclude_tables is not None:
                    ds["excludeTables"] = exclude_tables
                    updated = True

    if not updated:
        return {"status": "no_change", "message": "No dataSources found in definition"}

    removed = len(exclude_tables) if exclude_tables else 0
    print(f"[fix] Schema scope updated: {removed} tables excluded", file=sys.stderr)
    return update_agent_definition(workspace_id, artifact_id, token, parts)


# ── Master Apply Function ─────────────────────────────────────────

def apply_all_fixes(workspace_id, artifact_id, token, remediation_output, dry_run=True):
    """
    Apply all remediation artifacts to a Data Agent.

    remediation_output: dict with keys:
      - optimized_instructions: str
      - verified_answers: list of {question, dax}
      - schema_scope: list of table names to include
      - exclude_tables: list of table names to exclude (optional)

    dry_run=True: preview only, no writes
    dry_run=False: actually update the agent in Fabric
    """
    if not REQUESTS_AVAILABLE:
        return {"error": "requests library not available"}

    result = {
        "dry_run": dry_run,
        "instructions": None,
        "verified_answers": None,
        "schema_scope": None,
        "errors": [],
    }

    remediation = remediation_output or {}

    # 1. Instructions
    new_instructions = remediation.get("optimized_instructions")
    if new_instructions:
        truncated = len(new_instructions) > MAX_INSTRUCTION_CHARS
        char_count = min(len(new_instructions), MAX_INSTRUCTION_CHARS)
        result["instructions"] = {
            "char_count": char_count,
            "truncated": truncated,
            "original_length": len(new_instructions),
        }
        if not dry_run:
            r = apply_optimized_instructions(workspace_id, artifact_id, token, new_instructions)
            result["instructions"]["apply_result"] = r
            if "error" in r:
                result["errors"].append(f"Instructions: {r['error']}")

    # 2. Verified Answers
    vas = remediation.get("verified_answers")
    if vas and isinstance(vas, list) and len(vas) > 0:
        result["verified_answers"] = {
            "count": len(vas),
            "questions": [va.get("question", "")[:80] for va in vas[:10]],
        }
        if not dry_run:
            r = apply_verified_answers(workspace_id, artifact_id, token, vas)
            result["verified_answers"]["apply_result"] = r
            if "error" in r:
                result["errors"].append(f"Verified Answers: {r['error']}")

    # 3. Schema Scope
    include_tables = remediation.get("schema_scope")
    exclude_tables = remediation.get("exclude_tables")
    if include_tables or exclude_tables:
        result["schema_scope"] = {
            "include_count": len(include_tables) if include_tables else 0,
            "exclude_count": len(exclude_tables) if exclude_tables else 0,
            "include_tables": include_tables[:20] if include_tables else [],
            "exclude_tables": exclude_tables[:20] if exclude_tables else [],
        }
        if not dry_run:
            r = apply_schema_scope(workspace_id, artifact_id, token, include_tables, exclude_tables)
            result["schema_scope"]["apply_result"] = r
            if "error" in r:
                result["errors"].append(f"Schema Scope: {r['error']}")

    result["success"] = len(result["errors"]) == 0
    action = "Preview" if dry_run else "Applied"
    summary_parts = []
    if result["instructions"]:
        summary_parts.append(f"Instructions: {result['instructions']['char_count']} chars")
    if result["verified_answers"]:
        summary_parts.append(f"VAs: {result['verified_answers']['count']}")
    if result["schema_scope"]:
        summary_parts.append(f"Schema: {result['schema_scope'].get('exclude_count', 0)} excluded")
    result["summary"] = f"{action}: {', '.join(summary_parts)}" if summary_parts else f"{action}: no changes"

    print(f"[fix_applicator] {result['summary']}", file=sys.stderr)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    # Read remediation JSON from stdin
    remediation = json.loads(sys.stdin.read())
    result = apply_all_fixes(args.workspace_id, args.artifact_id, args.token,
                             remediation, args.dry_run)
    print(json.dumps(result, indent=2))
