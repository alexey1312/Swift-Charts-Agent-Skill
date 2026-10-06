# Probes

Programs that produced the numbers in `skills/*/references/measured-behavior.md`,
one for each skill.
They are committed so the figures can be re-derived rather than trusted.

## `masking_probe.swift`

Renders small Swift Charts charts on macOS with `ImageRenderer`,
compares them pixel by pixel,
and hosts some in an offscreen window to read their `ChartProxy`.

```bash
xcrun swiftc -O -suppress-warnings scripts/probes/masking_probe.swift -o "$TMPDIR/masking_probe"
"$TMPDIR/masking_probe"                              # the report
"$TMPDIR/masking_probe" --png "$TMPDIR/probe-png"    # and every render
```

It prints five sections, matching the masking skill's `measured-behavior.md` §1–§5:
series joins, mask edges, automatic domains, selection values, gradient stops.
It needs macOS 15 or later (vectorized plots) and writes nothing unless `--png` is given.

## `hexagon_probe.swift`

Renders grids of hexagon symbols on macOS with `ImageRenderer`,
counts the pixels no cell covers and the pixels two cells cover,
hosts some charts in an offscreen window to read their `ChartProxy` and geometry,
and runs the binning and map-projection arithmetic.

```bash
xcrun swiftc -O -suppress-warnings scripts/probes/hexagon_probe.swift -o "$TMPDIR/hexagon_probe"
"$TMPDIR/hexagon_probe"                              # the report
"$TMPDIR/hexagon_probe" --png "$TMPDIR/hexagon-png"  # and every render
```

It prints eleven sections, matching the heatmap skill's `measured-behavior.md` §1–§11:
the symbol's drawing box, tiling, plot proportions, automatic domains, clipping,
binning, color scales, the legend, ground area, area cells,
and a size that follows the plot.
It needs macOS 15 or later and writes nothing unless `--png` is given.
