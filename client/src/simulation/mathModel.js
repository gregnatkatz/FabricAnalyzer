// Pure synchronous JavaScript — no async, no API call, no side effects
// Must update UI within 100ms of any toggle

import { FIXES, CAPS, FLOOR_MS } from '../constants/fixes';

/**
 * Simulate projected latency for a set of traces with selected fixes applied.
 * @param {Array} traces - Array of trace objects with bd_schema, bd_nldax, bd_exec, total_ms
 * @param {Array} activeFixes - Array of fix key strings that are toggled on
 * @returns {Object} Simulation results with per-trace and aggregate metrics
 */
export function simulate(traces, activeFixes) {
  if (!traces || traces.length === 0) {
    return {
      traces: [],
      avgMs: 0,
      outlierMs: 0,
      passRate: 0,
      baselineAvgMs: 0,
      baselineOutlierMs: 0,
      baselinePassRate: 0,
      reductionPct: 0,
      perFix: {},
    };
  }

  // Compute cumulative reduction factors with caps
  let schemaR = 0;
  let daxR = 0;
  let execR = 0;

  for (const fixKey of activeFixes) {
    const fix = FIXES[fixKey];
    if (!fix) continue;
    schemaR += fix.schemaF;
    daxR += fix.daxF;
    execR += fix.execF;
  }

  // Apply caps
  schemaR = Math.min(schemaR, CAPS.schema);
  daxR = Math.min(daxR, CAPS.dax);
  execR = Math.min(execR, CAPS.exec);

  // Compute per-trace projections
  const projectedTraces = traces.map(trace => {
    const baseSchema = trace.bd_schema || 0;
    const baseDax = trace.bd_nldax || 0;
    const baseExec = trace.bd_exec || 0;
    const baseOther = trace.total_ms - baseSchema - baseDax - baseExec;

    const projSchema = baseSchema * (1 - schemaR);
    const projDax = baseDax * (1 - daxR);
    const projExec = baseExec * (1 - execR);
    const projTotal = Math.max(projSchema + projDax + projExec + Math.max(baseOther, 0), FLOOR_MS);

    return {
      ...trace,
      projected_ms: Math.round(projTotal),
      delta_ms: Math.round(trace.total_ms - projTotal),
      reduction_pct: trace.total_ms > 0
        ? Math.round(((trace.total_ms - projTotal) / trace.total_ms) * 100)
        : 0,
    };
  });

  // Aggregate metrics
  const baselineAvgMs = Math.round(traces.reduce((s, t) => s + t.total_ms, 0) / traces.length);
  const baselineOutlierMs = Math.max(...traces.map(t => t.total_ms));
  const baselinePassRate = Math.round(
    (traces.filter(t => t.total_ms < 20000).length / traces.length) * 100
  );

  const avgMs = Math.round(projectedTraces.reduce((s, t) => s + t.projected_ms, 0) / projectedTraces.length);
  const outlierMs = Math.max(...projectedTraces.map(t => t.projected_ms));
  const passRate = Math.round(
    (projectedTraces.filter(t => t.projected_ms < 20000).length / projectedTraces.length) * 100
  );
  const reductionPct = baselineAvgMs > 0
    ? Math.round(((baselineAvgMs - avgMs) / baselineAvgMs) * 100)
    : 0;

  // Per-fix individual contributions
  const perFix = {};
  for (const fixKey of Object.keys(FIXES)) {
    const fix = FIXES[fixKey];
    const singleSchemaR = Math.min(fix.schemaF, CAPS.schema);
    const singleDaxR = Math.min(fix.daxF, CAPS.dax);
    const singleExecR = Math.min(fix.execF, CAPS.exec);
    const singleAvg = Math.round(
      traces.reduce((s, t) => {
        const bs = t.bd_schema || 0;
        const bd = t.bd_nldax || 0;
        const be = t.bd_exec || 0;
        const bo = t.total_ms - bs - bd - be;
        const proj = Math.max(
          bs * (1 - singleSchemaR) + bd * (1 - singleDaxR) + be * (1 - singleExecR) + Math.max(bo, 0),
          FLOOR_MS
        );
        return s + proj;
      }, 0) / traces.length
    );
    perFix[fixKey] = {
      avgMs: singleAvg,
      reductionMs: baselineAvgMs - singleAvg,
      reductionPct: baselineAvgMs > 0
        ? Math.round(((baselineAvgMs - singleAvg) / baselineAvgMs) * 100)
        : 0,
    };
  }

  return {
    traces: projectedTraces,
    avgMs,
    outlierMs,
    passRate,
    baselineAvgMs,
    baselineOutlierMs,
    baselinePassRate,
    reductionPct,
    perFix,
  };
}
