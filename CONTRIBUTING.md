# Contributing

Thanks for helping keep these skills accurate.

## Good contributions

- **Measurements on iOS.**
  The probes run on macOS (each skill's `measured-behavior.md` › Scope).
  A run of the same comparisons on an iOS simulator or device —
  especially of what the built-in selection gesture reports past the plot's edge,
  and of what VoiceOver reads — is the most useful thing missing.
- **SDK updates.**
  When a new Xcode ships, run each skill's SDK check
  (`charts_sdk_check.py`, `heatmap_sdk_check.py`) and `scripts/typecheck_samples.py`,
  update the snapshot in each `api-availability.md`, and say which Xcode build you checked.
- **Scanner rules.**
  Add a `Rule` to the skill's scanner with a source,
  a positive and a negative test in its `tests/test_*_scan.py`,
  and a row in the skill's section of `CHECKS.md`.
- **False positives** found on real projects, with a minimal reproduction.
- **Evals** for behavior the skill gets wrong:
  a case in `skills/<skill>/evals/evals.json` with a small fixture project
  that typechecks, or a query in `trigger-evals.json`.

## Rules

- Guidance traces to an Apple session, a documentation page, the SDK,
  or the probe. Label anything else as *inference*.
- Third-party posts are credited in `sources.md`;
  their code is not copied.
- No third-party Python dependencies.

## Evaluating a change

The skills are developed with Anthropic's
[skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator):
run each eval with and without the skill, grade the expectations,
aggregate a benchmark, and review outputs in its viewer.
Trigger accuracy is tuned with its `run_loop` against `trigger-evals.json`
(run it with one worker: parallel workers share one commands directory
and report false negatives).
Keep workspaces outside the repository (`*-workspace/` is ignored).

The same cases also run through `claude plugin eval`.
`scripts/build_plugin_evals.py` stages a copy of the plugin without any `evals/`
directory — the expectations are the answer key —
and writes one `case.yaml` per case next to it, outside the repository:

```bash
python3 scripts/build_plugin_evals.py "$TMPDIR/charts-plugin-eval"
claude plugin eval "$TMPDIR/charts-plugin-eval" --trust-plugin --scaffold \
  --allow-tools Bash Edit Write --model "$AGENT_MODEL" --judge-model "$JUDGE_MODEL" \
  --no-publish --max-cost-usd 20 --json "$TMPDIR/charts-eval.json"
```

Set `AGENT_MODEL` to the model under test and `JUDGE_MODEL` to the grader,
and keep both fixed across runs you compare.
`--no-publish` keeps the HTML report local; without it the report is published.
The runner's `costUsd` leaves out the judge,
so set `--max-cost-usd` to about two thirds of the real budget.
Before trusting a run, read a few failing transcripts:
a grader can be wrong as easily as an agent.

## Checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/typecheck_samples.py
xcrun swiftc -O -suppress-warnings scripts/probes/masking_probe.swift -o "$TMPDIR/masking_probe" && "$TMPDIR/masking_probe"
xcrun swiftc -O -suppress-warnings scripts/probes/hexagon_probe.swift -o "$TMPDIR/hexagon_probe" && "$TMPDIR/hexagon_probe"
```

## Releasing

1. Bump the version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   `.cursor-plugin/plugin.json` and `agents/openai.yaml` (the tests check they agree)
   and merge it to `main`.
2. Tag that commit and push the tag:

   ```bash
   git tag v1.1.0 && git push origin v1.1.0
   ```

The `Release` workflow refuses a tag that does not match the plugin version,
re-runs the tests, builds one `.skill` archive per skill with
`scripts/package_skills.py`, and publishes a GitHub release.
