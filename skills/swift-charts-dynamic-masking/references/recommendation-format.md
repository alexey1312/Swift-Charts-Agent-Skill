# Recommendation format

Use this shape for every recommendation,
whether it comes from the scanner or from reading code.
Each item has a stable ID the developer can approve,
and nothing changes until they do.

## Per item

```markdown
### CHART-02 · Give the two line copies their own series

- **Finding:** `CHART001:Sources/Activity/TrendChart.swift:48` — the second `LinePlot(activity, …)` has no `series:`
- **What goes wrong:** both copies are one series, so a line runs from the last day
  back to the first whenever the dimmed copy shows.
- **Source:** Apple documentation › LineMark (series); measured-behavior.md §1
- **Change:** `series: .value("Layer", "Dimmed")` on the dimmed copy,
  `series: .value("Layer", "Active")` on the masked one.
- **SDK:** `LinePlot(_:x:y:series:)` is iOS 18; deployment target 18.0 — no gate needed
- **Risk:** low — no layout change; snapshot references with a selection move.
- **Verify:** states S4 and S1 (`selection-state-matrix.md`).
- **Status:** proposed
```

## Rules

- **IDs are stable** across a session (`CHART-01`, `CHART-02`, …).
  A scanner finding keeps its own ID (`CHART001:path:line`) in the *Finding* line.
- **One source per item:** a session and timestamp, a documentation page,
  or a section of `measured-behavior.md`.
  If the advice is your own reasoning, label it *inference* and say what it rests on.
  The article that introduced the technique is background, not a citation —
  cite what the claim rests on.
- **Say what you did not verify.**
  "It builds" is not "it looks right".
  A state not rendered is *not verified*, with the step that would verify it.
- **Order:** correctness (joined lines, cut points, rescaling, wrong labels),
  then the technique (replacing sliced data or a hand-rolled gesture),
  then polish (single mask rectangle, accessibility, gradients, the popover).
- **Status values:** `proposed`, `approved`, `applied`, `verified`, `blocked`
  (with the reason), `declined`, `kept` (left as is, with the reason).
- **Batch approval is fine** when the developer names it ("apply CHART-01 to CHART-04").
  "Fix everything" before a plan exists means: produce the plan.

## Report skeleton

```markdown
# Chart masking — <screen or chart>

Toolchain: Xcode <version> (<build>), iOS <sdk> SDK · Deployment target: iOS <n>
Scan: charts_scan <version>, <n> files, <n> with charts

## Summary
<What the chart should do, what it does now, what the deployment target allows.>

## Correctness
## Technique
## Polish
## Kept as is
## Not verified
```
