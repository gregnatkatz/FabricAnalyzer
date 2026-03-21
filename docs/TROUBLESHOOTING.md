# Troubleshooting Guide

Common issues and solutions when running FabricAnalyzer.

---

## Connection Issues

### Backend status light is red

**Symptom**: StatusHeader shows red for "Backend".

**Cause**: Express server not running on port 3001.

**Fix**:
```bash
cd server && node proxy.js
```
Check for port conflicts: `lsof -i :3001`

### LLM Agents status light is red

**Symptom**: StatusHeader shows red for "LLM Agents".

**Cause**: Azure AI endpoint unreachable or credentials invalid.

**Check**:
```bash
curl -s -m 10 "${LLM_ENDPOINT}/openai/deployments/${LLM_MODEL}/chat/completions?api-version=2025-01-01-preview" \
  -H "api-key: ${LLM_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hello"}],"max_tokens":5}'
```

**Common causes**:
- `LLM_API_KEY` not set in `server/.env`
- API key auth disabled on Azure AI resource (Entra ID only)
- Wrong model deployment name
- Endpoint URL missing `/openai/v1` suffix

### ChromaDB status light is red

**Symptom**: StatusHeader shows red for "ChromaDB".

**Cause**: ChromaDB not initialized or path incorrect.

**Fix**:
```bash
cd server && python3 -c "from knowledge.embedder import embed_knowledge; embed_knowledge()"
```

Verify: `ls -la chroma_db/` should show persistent storage files.

### Fabric status light is red

**Symptom**: StatusHeader shows red for "Fabric".

**Cause**: No Fabric token or token expired.

**Fix**: Re-authenticate via OAuth or paste a fresh token manually. Fabric tokens expire after 1 hour.

---

## Pipeline Issues

### Pipeline hangs or times out

**Symptom**: Workflow tab shows an agent stuck in "running" state for >3 minutes.

**Cause**: LLM endpoint not responding. Node.js fetch hangs on some Azure AI endpoints.

**Fix**: The proxy already uses `curl` via `execSync` (180s timeout). If still hanging:
1. Check Azure AI endpoint health in Azure Portal
2. Try a different model (e.g., switch from GPT-5.4 Pro to DeepSeek V3.2)
3. Run in sample mode (no LLM needed for deterministic rules)

### "No traces available" error

**Symptom**: Pipeline returns immediately with no findings.

**Cause**: No trace data collected yet.

**Fix**:
1. Go to Connect tab
2. Either load Sample Dataset or connect to Fabric and collect traces
3. Verify traces exist: check Traces tab shows data

### Findings tab shows 0 findings

**Symptom**: Pipeline completes but Findings tab is empty.

**Cause**: Findings not persisted from pipeline output to session state.

**Check**: Look at Workflow tab logs — each agent should report finding counts. If agents report findings but Findings tab is empty, the issue is in the frontend state update.

### GPT-5.4 Pro returns errors

**Symptom**: `model_not_found` or `unsupported_model` errors when using GPT-5.4 Pro.

**Cause**: GPT-5.4 Pro is a reasoning model that only supports the `/responses` API, not `/chat/completions`.

**Fix**: Use DeepSeek V3.2 Speciale instead. GPT-5.4 Pro requires a separate code path (not yet implemented).

---

## Monte Carlo Issues

### Simulation shows 0% reduction

**Symptom**: All fixes toggled on but projected latency unchanged.

**Cause**: Traces have zero values for `bd_schema`, `bd_nldax`, or `bd_exec`.

**Fix**: Verify trace data has phase breakdowns. Auto-generated traces should have these. If using real Fabric traces, the breakdown fields may need to be estimated.

### Very wide P10-P90 range

**Symptom**: Monte Carlo shows large spread between P10 and P90.

**Cause**: Normal for fixes with high standard deviation (e.g., `verified_answers` has stddev 0.15).

**Interpretation**: Wide range = less certainty about the fix's impact. Narrow range = high confidence. Check the confidence column in per-fix results.

---

## Authentication Issues

### OAuth popup blocked

**Symptom**: MSAL login popup doesn't appear or is blocked.

**Cause**: Browser popup blocker or headless browser environment.

**Workaround**: Use manual token paste:
1. Get a token from `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`
2. Paste it in the Connect tab's manual token field
3. For Fabric scope: `https://analysis.windows.net/powerbi/api/.default`

### "Token tenant does not match resource tenant"

**Symptom**: Azure AI calls fail with tenant mismatch error.

**Cause**: Fabric workspace and Azure AI resource are in different Azure AD tenants.

**Fix**: Use API key auth instead of Azure AD tokens. Enable API key auth on the Azure AI resource in Azure Portal.

### Device code flow fails

**Symptom**: `az login --use-device-code` succeeds but API calls still fail.

**Cause**: Logged into wrong tenant.

**Fix**: Specify tenant explicitly:
```bash
az login --use-device-code --tenant {correct-tenant-id}
```

---

## Setup Issues

### `chromadb` import error

**Symptom**: `ModuleNotFoundError: No module named 'chromadb'`

**Fix**:
```bash
pip install chromadb sentence-transformers
```

### `puppeteer` PDF export fails

**Symptom**: PDF export returns error or empty PDF.

**Cause**: Puppeteer's Chromium not installed.

**Fix**:
```bash
cd server && npx puppeteer install chromium
```

### Python not found

**Symptom**: Pipeline fails with "python3 not found".

**Fix**: Set `PYTHON_PATH` in `server/.env` to your Python 3 path:
```bash
PYTHON_PATH=/usr/bin/python3
# or
PYTHON_PATH=python
```

### Port already in use

**Symptom**: `EADDRINUSE: address already in use :::3001`

**Fix**:
```bash
# Find and kill the process
lsof -i :3001
kill -9 <PID>
# Or use a different port
PORT=3002 node proxy.js
```

---

## Data Issues

### Sample dataset has different findings than expected

**Symptom**: Sample mode shows different finding count than documented.

**Cause**: Sample dataset is pre-built with 25 known issues. The deterministic rules detect ~20 of them (80% detection rate). The remaining 5 require LLM analysis.

### Traces show unrealistic latency values

**Symptom**: Auto-generated traces all have suspiciously round numbers.

**Cause**: Normal for auto-generated traces. They use domain-specific templates with randomized values within realistic ranges. Real Fabric traces will have more natural variation.

### ChromaDB shows fewer than 538 chunks

**Symptom**: Health endpoint reports fewer chunks than expected.

**Cause**: Embedding process was interrupted or issue catalog was modified.

**Fix**: Re-run embedding:
```bash
cd server && python3 -c "from knowledge.embedder import embed_knowledge; embed_knowledge()"
```
Expected: 38 doc chunks + 500 issue catalog = 538 total.
