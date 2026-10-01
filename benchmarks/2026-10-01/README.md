# Benchmark — 2026-10-01

Five cases, run with `claude plugin eval` on plugin version **1.0.0**,
Claude Code 2.1.285, against **Xcode 27.1 (27A9269)** and the iOS 27.1 SDK.
One agent model and a separate, smaller judge model, both fixed for the whole run;
three runs per arm, three judge votes per criterion.
500 s at four runs in parallel, **$17.33** — $11.89 for the agents and $5.44 for the judge.

```bash
python3 scripts/build_plugin_evals.py "$TMPDIR/charts-plugin-eval"
claude plugin eval "$TMPDIR/charts-plugin-eval" --trust-plugin --scaffold \
  --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \
  --no-publish --runs 3 -j 4 --max-cost-usd 20 --threshold 0
```

`aggregate-result.json` is the runner's result with the transcripts and local paths removed:
scores, every judge vote, turns and cost per run, and each criterion as it was graded.

| Case | With skill | Without skill | Δ |
| --- | --- | --- | --- |
| `tradingview-scrub-plan` | **0.95** (2/3) | 0.38 (0/3) | **+0.57** |
| `tooltip-wrong-day` | **1.00** (3/3) | 0.67 (0/3) | **+0.33** |
| `actual-and-forecast-one-line` | **1.00** (3/3) | 0.67 (1/3) | **+0.33** |
| `ios16-deployment-target` | **0.83** (2/3) | 0.75 (0/3) | +0.08 |
| `joined-line-and-cut-dots` | 0.95 (2/3) | **1.00** (3/3) | −0.05 |
| **Mean** | **0.95** | 0.69 | **+0.25** |

Scores are the mean share of criteria passed; the count is runs that passed every criterion.

## Read the with-skill failures before citing these numbers

Four with-skill runs failed a criterion.
Three of them were the judge, not the agent:

- **`tradingview-scrub-plan` #1, e07** (3 of 3 votes *fail*):
  the plan numbers its items CHART-01 to CHART-07 and ends by asking which to apply —
  exactly what the criterion asks.
  The criterion also said "no file was modified", which a judge reading only the final
  message cannot confirm; that clause has since been removed.
- **`joined-line-and-cut-dots` #0, e04** (2 of 3 *fail*):
  the final message explains that both copies "counted as one line"
  and that "the mask started exactly on the first day and ended exactly on the last day".
  The criterion has since been reworded to accept any words for the two causes.
- **`ios16-deployment-target` #0, e03** (2 of 3 *fail*):
  the plan uses `LineMark` copies with distinct series, a mask,
  and an overlay `DragGesture`; its one iOS 17 item is gated behind `if #available`.
  It meets the criterion as written.

The fourth is real:
in the same run the agent could not run `xcodebuild` (the sandbox blocks its cache)
and reported no toolchain at all (e04).
The skill now tells it to fall back to `xcrun --show-sdk-version` and the SDK check.
The same run also claimed `plotAreaFrame` warns at an iOS 16 target;
`swiftc -typecheck` shows it warns only from iOS 17, and the skill now says so.

Hand-correcting the three judge errors gives the skill **0.98**.
The baseline's failures were spot-checked rather than all re-read:
the ones checked were real (no toolchain reported in any iOS 16 run;
the forecast fix recommending a duplicated boundary point instead of masked copies),
but the baseline was not hand-corrected, so the honest comparison is
**0.95 against 0.69** as graded.

These two skill edits and the two reworded criteria came after the run;
the numbers above are from the text as it was.

## What the Δ measures

- **Where the skill adds most, it adds a workflow the baseline does not have:**
  item IDs and an approval gate, citations,
  replacing a hand-rolled gesture with `chartXSelection`, snapping the selection,
  and an explicit, padded domain with a mask that starts at the plot's edge
  (`tradingview-scrub-plan`).
- **Some criteria measure the skill's own conventions**, which a baseline cannot be
  expected to follow.
  `tooltip-wrong-day`'s whole Δ is one such criterion — a citation:
  every baseline run found the bug and the right fix.
- **Where the baseline already knows, the skill adds nothing.**
  Opus fixed the joined line and the cut-off dots without the skill in all three runs
  (`joined-line-and-cut-dots`), and planned a sound iOS 16 version every time,
  with a hard-stop gradient instead of masks, which the criterion accepts;
  what the baseline missed there was reporting the toolchain.
- **Wrong answers seen without the skill**, in the pilot:
  one run said `ChartContent.mask` needs iOS 17 (it is iOS 16),
  and one said two `LinePlot`s without a series "render as separate lines" —
  the probe measured that they merge (`measured-behavior.md` §1).

## The pilot found a defect in the suite itself

A one-run pilot ($5.17) preceded this run.
The `actual-and-forecast-one-line` case then asked about a "visible gap at today".
Rendering the fixture showed there is no gap:
the two filtered `LinePlot`s without series merge into one line,
and the dashed half is drawn solid.
Both arms had accepted the false premise,
and the with-skill run passed a criterion by explaining a gap that does not exist.
The prompt now describes the real symptom,
the probe measures the case (`measured-behavior.md` §1),
and the scanner reports it (`CHART010`).

## Cost

| | Turns | Duration | Agent cost per run | Judge cost per run |
| --- | --- | --- | --- | --- |
| With skill | 7–13 (median 8) | 31–106 s | $0.47 | $0.21 |
| Without | 3–10 (median 4) | 26–113 s | $0.33 | $0.15 |

The skill about doubles the turns — it runs the scan and reads references —
and costs about 40 % more per run.

## Not measured

- Trigger accuracy (`trigger-evals.json`): not run.
- Repeats after the post-run edits.
