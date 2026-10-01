# Selection state matrix

A selection-driven chart has a handful of states where it goes wrong.
Verify the ones a change touches,
and report every other one as *not verified*.

Selection comes from a gesture, which a preview or snapshot test cannot perform.
Give the chart an initial selection
(`masking-code.md` › Pinning a state)
and render each state directly;
use a run on a simulator or device for the gesture itself.

| ID | State | Pin it with | Look for |
| --- | --- | --- | --- |
| S1 | Nothing selected | `nil` | Identical to the chart without the effect: no dimmed copy showing, first and last symbols whole (`measured-behavior.md` §2). |
| S2 | First point | the first day | Only the first point bright; nothing to the left of it cut. |
| S3 | Between two points, past the midpoint | e.g. day 2.6 | Rule, mask edge and popover all on day 3; the popover's date and value from the same day (`CHART008`). |
| S4 | A middle point | a data day | Bright up to the point, dimmed after it; no line from the last point back to the first (`CHART001`). |
| S5 | Last point | the last day | Everything bright up to the last point; popover inside the chart (`overflowResolution`). |
| S6 | Past the leading edge | three days before the data | Snapped to the first point; the chart did not rescale or shift (`measured-behavior.md` §3–4). |
| S7 | Past the trailing edge | three days after the data | Snapped to the last point; no rescale. |
| S8 | Gesture ends | — (a run) | What the chart returns to when the finger lifts, and whether that is what the design wants. |
| S9 | Dark mode, increased contrast | `.preferredColorScheme(.dark)` | The dimmed part still readable against the background. |
| S10 | VoiceOver | — (a run) | Each point read once, from the active copy (`CHART006`; *inference*, never measured). |
| S11 | Large data | a few thousand points | Dragging stays smooth (vectorized plots, WWDC24 10155, 0:51). |
| S12 | Range (range selection only) | a range | Bright between the snapped ends only; both ends whole. |

S1–S7 and S12 render from a pinned value.
S8, S10 and S11 need the gesture, so they need a run;
on macOS the gesture is hover (WWDC23 10037, 6:59), so S8 there means the pointer
leaving the plot.
