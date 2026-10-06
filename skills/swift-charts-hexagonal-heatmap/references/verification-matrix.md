# Verification matrix

A hexagonal heatmap goes wrong in a handful of states.
Verify the ones a change touches,
and report every other one as *not verified*.

The cell size comes from the plot's measured size,
and `ImageRenderer` drew the settled size on its first pass
(`measured-behavior.md` §11),
so a preview or a snapshot test renders V1–V7 directly.
Give the heatmap fixed bins —
the spiral preview in `heatmap-code.md` › Previews, or a small fixture —
so that each render is the same.

| ID | State | Render it with | Look for |
| --- | --- | --- | --- |
| V1 | Default size | the screen's own frame | Neighboring hexagons touch or keep one even gap; no white bands between rows, no dark overlap (`measured-behavior.md` §2). |
| V2 | Narrow | a 320 pt wide frame | The same tiling at a smaller size; the plot keeps the domains' ratio (§3). |
| V3 | Wide or resized | iPad width, landscape, Split View | The size follows the plot (§11); rows do not overlap. |
| V4 | Axes and legend shown | the chart as shipped | No cell over the axis labels (§5); a color bar with values below the plot (§8). |
| V5 | Edge of the domain | data that reaches past the domain | Cells cut at the plot's edge, not drawn outside it (§5). |
| V6 | Skewed counts | a few cells with thousands, most with one or two | Low counts still visible; the hot spots still the warmest color (§7). |
| V7 | Dark mode, increased contrast | `.preferredColorScheme(.dark)` | The faint end of the ramp and the outline still readable against the background (WWDC22 110340, 21:35). |
| V8 | VoiceOver | — (a run) | One element for each cell, with its place first and its count as the value (WWDC22 110340, 17:18; never measured here). |
| V9 | Large data | the full data set | Binning runs once, not on every render; scrolling and resizing stay smooth (WWDC24 10155, 12:14). |
| V10 | Empty or single cell | no observations; one observation | No crash; the color domain is still a range (`max(1, …)`). |

V1–V7 and V10 render from fixed bins.
V8 and V9 need a run on a device or simulator.
