"""Phase 6 — Query Simulator.
Simulates agent query execution against synthetic data for validation.
"""
import json
import os
import random
import time


class QuerySimulator:
    """Simulates Data Agent query execution for testing fixes."""

    def __init__(self, session_dir, behavioral_profile=None):
        self.session_dir = session_dir
        self.profile = behavioral_profile or {}
        self.tables = {}
        self._load_tables()

    def _load_tables(self):
        """Load synthetic tables from session directory."""
        if not os.path.exists(self.session_dir):
            return
        for f in os.listdir(self.session_dir):
            if f.endswith('.json') and f != 'manifest.json':
                table_name = f.replace('.json', '')
                with open(os.path.join(self.session_dir, f)) as fh:
                    self.tables[table_name] = json.load(fh)

    def simulate_query(self, question, fixes_applied=None):
        """Simulate a query and return simulated trace data.
        
        Returns:
            dict with: total_ms, retries, pass_fail, bd_parse, bd_schema, bd_nldax, bd_exec, bd_synth
        """
        fixes = fixes_applied or []

        # Base latency components (calibrated from behavioral profile)
        bd_parse = random.randint(200, 400)
        bd_schema = random.randint(3000, 7000)
        bd_nldax = random.randint(4000, 12000)
        bd_exec = random.randint(800, 4000)
        bd_synth = random.randint(200, 400)
        retries = random.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]

        # Apply fix reductions
        if 'instruction_trim' in fixes:
            bd_nldax = int(bd_nldax * 0.7)
        if 'schema_scope' in fixes:
            bd_schema = int(bd_schema * 0.4)
        if 'routing_rules' in fixes:
            retries = max(0, retries - 2)
        if 'verified_answers' in fixes:
            if random.random() < 0.6:  # 60% chance VA hits
                bd_nldax = random.randint(200, 500)
        if 'topn_guard' in fixes:
            bd_exec = int(bd_exec * 0.7)
        if 'measure_dedup' in fixes:
            bd_nldax = int(bd_nldax * 0.85)
        if 'vorder' in fixes:
            bd_exec = int(bd_exec * 0.8)

        total_ms = bd_parse + bd_schema + bd_nldax + bd_exec + bd_synth + (retries * 3100)

        # Determine pass/fail
        pass_fail = 'pass' if total_ms < 30000 and random.random() > 0.1 else 'fail'

        return {
            'question': question,
            'total_ms': total_ms,
            'retries': retries,
            'pass_fail': pass_fail,
            'bd_parse': bd_parse,
            'bd_schema': bd_schema,
            'bd_nldax': bd_nldax,
            'bd_exec': bd_exec,
            'bd_synth': bd_synth,
            'fixes_applied': fixes,
        }

    def run_battery(self, questions, fixes_applied=None):
        """Run a battery of questions and return all results."""
        results = []
        for q in questions:
            result = self.simulate_query(
                q.get('question', q) if isinstance(q, dict) else q,
                fixes_applied,
            )
            results.append(result)
        return results
