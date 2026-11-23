# CAPE-Graph v0.5 — Release audit

- Source date: 2026-11-24, fixed-seed fully synthetic experiments.
- New: `capegraph/mixed.py` exact private-randomness two-prior robust policy solver with rational primal/dual certificate.
- 105/105 framework tests and 97/97 pre-existing domain research tests locally rerun (202 total); results: `FULL_REPLAY_LOG.txt`.
- Independent SciPy LP test: 100 synthetic games; arithmetic in production solver uses stdlib only.
- Full v0.4 ablation, exact planner, adaptive and robust regressions kept in the pack.
- New exact mixed experiment: `experiments/mixed_results.json`; 180 unchanged v0.4 seeds, 240 deliberately conflict-enriched seeds, one non-rectangular multistep control; every one has an exact primal/dual certificate and replay.
- Out of scope: external model-agent rollouts, calibrated service priors, proof of total service side effects, official PALE acceptance, paper coauthorship or SOTA ranking.
- Command: `python run_all.py` (prior_97 requires NumPy; SciPy used only for an independent optional test).
