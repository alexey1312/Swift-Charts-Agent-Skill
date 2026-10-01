# Checks

Every automated rule in `charts_scan.py`, and the checks that need a person.
Matches are heuristics:
the agent reads the chart before a finding becomes a recommendation.

## Automated

| Rule | Severity | Finds | Source |
| --- | --- | --- | --- |
| `CHART001` | high | Two line plots or marks of the same data whose `series:` is missing or equal — drawn as one line, joined from the last point back to the first | *LineMark* documentation; `measured-behavior.md` §1 |
| `CHART002` | medium | Data filtered or cut with `prefix(while:)` by the selection variable | *ChartContent.mask(content:)* documentation; `measured-behavior.md` §3 |
| `CHART003` | medium | A mask rectangle that starts on the first element, or falls back to the last — the edge symbols lose half their ink | `measured-behavior.md` §2 |
| `CHART004` | low | `RectanglePlot(data, …)` with constant bounds inside a mask — one rectangle per element where one `RectangleMark` does | `measured-behavior.md` §2; WWDC24 10155, 11:34 |
| `CHART005` | medium | The raw selection used as a mark's value with no clamp or snap — values past the data rescale an automatic domain | WWDC23 10037, 5:47; `measured-behavior.md` §3–4 |
| `CHART006` | low | More than one layer of the same data readable by VoiceOver (*inference*) | WWDC22 10137, 4:21; *ChartContent.accessibilityHidden(_:)* documentation |
| `CHART007` | medium | Layers of the same data with different interpolation methods | WWDC22 10137, 7:06 |
| `CHART008` | low | An annotation that formats the raw selection | WWDC23 10037, 5:47 |
| `CHART009` | info | A `DragGesture` in `chartOverlay` converted with `proxy.value(atX:)` — keep it only for iOS 16 | WWDC23 10037, 5:26 and 5:34 |
| `CHART010` | high | Line plots of different data in one chart, none with a `series:` — merged into one line in one style (a dashed plot loses its dash) | *LineMark* documentation; `measured-behavior.md` §1 |

The scanner also reports the iOS deployment targets it finds
(`IPHONEOS_DEPLOYMENT_TARGET`, `Package.swift` platforms)
and an inventory of the chart APIs in use.

### Known limits

- Layers are matched by their data argument and their x and y key paths or
  properties. A `LineMark` inside `ForEach` has no data argument,
  so it is compared with every layer on the same x and y.
- `CHART003` follows an identifier one `let` back
  (`if let begin = days.first?.date`); deeper indirection is missed.
- `CHART005` accepts any `min`, `max` or `clamp` near an `onChange(of:)` of the
  selection as clamping.

## Manual

| Check | How |
| --- | --- |
| Selection states S1–S12 | `references/selection-state-matrix.md` |
| Every API above the deployment target is gated | `charts_sdk_check.py` against the scan's `ios_deployment_targets` |
| What VoiceOver reads | A run with VoiceOver; never measured by this repository |
