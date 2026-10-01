# Probes

Programs that produced the numbers in `skills/*/references/measured-behavior.md`.
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

It prints five sections, matching `measured-behavior.md` §1–§5:
series joins, mask edges, automatic domains, selection values, gradient stops.
It needs macOS 15 or later (vectorized plots) and writes nothing unless `--png` is given.
