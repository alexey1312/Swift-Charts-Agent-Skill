# Agent guidance

This repository contains Agent Skills that advise on and change Swift Charts code in iOS apps.

- **Phase 1 stays read-only.**
  `charts_scan.py` and `charts_sdk_check.py` must never write to the scanned project
  or the SDK; `test_scan_does_not_modify_files` guards the scanner.
- **Every rule cites a source.**
  A scanner rule's `source` names a session and timestamp (`WWDC23 10037 … m:ss`),
  an Apple documentation page (`Apple documentation › …`),
  or the probe (`Measured: scripts/probes/masking_probe.swift §n`);
  the metadata test enforces it.
- **Measurements outrank posts.**
  A *Measured* statement in a skill must be re-derivable by running
  `scripts/probes/masking_probe.swift`.
  Change the probe and `measured-behavior.md` together.
- **The SDK outranks samples.**
  Every Swift block in `skills/*/references/*.md` starts with
  `// typecheck: ios<N>` and must compile for iOS N and fail for iOS N−1
  (`python3 scripts/typecheck_samples.py`).
  A block that cannot be complete does not belong in a reference.
- **The skill's own code scans clean.**
  `OwnAdviceTests` scans every reference block; only `info` findings may remain.
- **Scanner changes need tests** for a positive and a negative case,
  and a row in `CHECKS.md`.
- **Behavior changes need evals.**
  Each skill keeps skill-creator evals in `skills/<skill>/evals/`
  (`evals.json` with fixture projects under `files/`, and `trigger-evals.json`).
  Fixture projects must typecheck at their deployment target.
  Re-run them with and without the skill before claiming an improvement;
  `scripts/package_skills.py` leaves `evals/` out of release archives.
- **Keep SKILL.md descriptions under 1024 characters**
  and the `name` equal to the directory name.
- **Rewrite, don't copy.**
  The article and its gist carry no licence;
  code here is written for this repository and credits the article as the origin
  of the technique.
- Keep the plugin version identical in `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json` and
  `agents/openai.yaml`.
  A GitHub release is cut by pushing a matching `vX.Y.Z` tag.
- Run before completing a change:

  ```bash
  python3 -m unittest discover -s tests -v
  python3 scripts/typecheck_samples.py
  ```
