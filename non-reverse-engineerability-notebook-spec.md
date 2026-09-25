# Non-Reverse-Engineerability Example Notebook (IEEE-118) Spec

**Status:** Draft
**Date:** 2026-09-25
**Domain:** Software Feature (example / documentation notebook)
**Tier:** B — Focused spec

---

## 1. Overview

The non-reverse-engineerability study measures how much a *pooling adversary*
— someone holding a batch of synthetic grids generated from one reference
network, plus the open source code — can recover about that reference when
the perturbation layer (`powergrid_synth.privacy`) is active. Today the study
exists only as a CLI script (`scripts/measure_topology_recovery.py`) and a
figure script (`scripts/make_recovery_figure.py`), while the docstrings of
`powergrid_synth/privacy/__init__.py` and `powergrid_synth/privacy/recovery.py`
already refer to an "evaluation notebook" that does not exist.

This spec defines that notebook: a self-contained, top-to-bottom runnable
Jupyter notebook at `examples/transmission/non_reverse_engineerability.ipynb`
that reproduces the study on the IEEE-118 bus system — same configuration,
same estimators, same figure — so a reader can see *how* the protection claims
in `docs/theory/perturbation.rst` are measured, and re-run them.

---

## 2. Goals

1. A reader can execute the notebook end to end (≈2 minutes on a laptop) and
   obtain the pooling-adversary results for IEEE-118 at strengths 0, 0.5, 1.0
   and 2.0.
2. With default settings, every number the notebook produces is identical to
   the JSON written by `scripts/measure_topology_recovery.py` with its default
   arguments.
3. The notebook explains the threat model, the batch design (one fixed noise
   seed per batch) and how to read each estimator, without asserting
   conclusions tied to specific measured numbers.
4. The notebook depends only on the public library API plus standard
   scientific packages — no imports from `scripts/`, no `sys.path`
   manipulation.

## 3. Non-Goals

- **No new analyses.** No pool-size curves, no noise-seed spread across
  batches, no per-level degree KS (`recover_degree_dist`), no additional
  parameters beyond the three the script perturbs.
- **No docs integration.** No `docs/examples/*.nblink`, no toctree entry in
  `docs/examples/transmission.rst`, no link from `docs/theory/perturbation.rst`.
- **No Colab twin** in `examples/colab/`.
- **No library changes** (`powergrid_synth/**`) and **no script changes**
  (`scripts/**`).
- **No distribution pipeline** — transmission / IEEE-118 only.
- **No interpretive claims** about which parameters are or are not protected
  on this run (see FR-10).

---

## 5. Requirements

### 5.1 Functional Requirements

| ID    | Requirement | Priority | Notes |
|-------|-------------|----------|-------|
| FR-01 | A single **settings cell** near the top defines every study parameter as a named constant: `REFERENCE_CASE = "case118"`, `N_GRIDS = 30`, `STRENGTHS = (0.0, 0.5, 1.0, 2.0)`, `BATCH_SEED = 4242`, `PERTURBED_PARAMETERS = ("node_count", "degrees_by_level", "diameters_by_level")`. Grid seeds are `range(N_GRIDS)`. | Must | Values mirror the script defaults exactly. |
| FR-02 | Load the reference with `pandapower.networks.case118()`, convert with `pandapower_to_nx`, extract reference parameters with `extract_topology_params_from_graph`, and display the true buses per level (`len(degrees_by_level[level])`) and true spans (`diameters_by_level`). | Must | Same path as the script's `main()`. |
| FR-03 | Markdown section explaining the threat model: single-sample vs pooling adversary, why perturbation noise is drawn once per batch (shared seed), and the "one batch per reference" caveat. Concise; defers detail to `docs/theory/perturbation.rst`. | Must | Paraphrase, don't copy the theory page. |
| FR-04 | A function `build_config(strength, batch_seed)` returning `None` for `strength <= 0`, else `{"strength": strength, "seed": batch_seed, "parameters": {name: {"mode": "perturb"} for name in PERTURBED_PARAMETERS}}`. | Must | Identical semantics to the script. |
| FR-05 | A function `generate_pool(reference_case, strength, n_grids, output_dir)` calling `powergrid_synth.transmission.synthesize.synthesize(mode="reference", reference_case=..., seed=grid_index, perturbation_config=build_config(strength, BATCH_SEED), output_dir=..., output_name=f"pool_{strength}_{grid_index}", export_formats=())` for each grid, with the synthesiser's stdout suppressed via `contextlib.redirect_stdout(io.StringIO())`. Shows lightweight progress (one line per strength is enough). | Must | `output_dir` is a temporary directory (`tempfile.TemporaryDirectory`) so nothing is written into the repo. |
| FR-06 | An inline helper `measure_spans_by_level(graph) -> list[int]`: span of each level = diameter of the largest connected component of that level's induced subgraph; `0` for empty levels or levels with < 2 nodes; levels indexed `0..max_level`. | Must | Behaviourally identical to the private `powergrid_synth.transmission.synthesize._measure_spans_by_level`; do **not** import the private function. |
| FR-07 | A function `measure(graphs, true_params)` returning, per strength, the same structure as the script: `node_count` per level from `recover_node_count` (mean, ci_lo, ci_hi, plus `true`, with `counts` dropped); `degrees_by_level.ks_distance` from `recover_degree_dist_full`; `diameters_by_level` per level with `mean` (`statistics.fmean`), `stdev` (`statistics.stdev`, `0.0` if one value) and `true`. Results are collected into a dict `results` with the same keys as the script's JSON (`reference_case`, `n_grids`, `perturbed_parameters`, `true_node_counts`, `true_spans`, `by_strength` keyed by `str(strength)`). | Must | Same schema allows direct comparison (FR-11). |
| FR-08 | Display the results as `pandas` DataFrames: (a) buses per level — rows = strength × level, columns = true, mean, ci_lo, ci_hi, mean/true; (b) degree KS distance per strength; (c) span per level — true, mean, stdev. | Must | Readable tables, not raw dict dumps. |
| FR-09 | Reproduce the 3-panel recovery figure inline, with the same layout and encodings as `scripts/make_recovery_figure.py`: (1) recovered/true buses per level with CI error bars and a dashed line at 1.0; (2) KS distance vs strength with a dotted "unperturbed" reference line at the strength-0 value; (3) realised span ± stdev at the level with the largest true span, dashed line at the true span. Same colours as the script. The figure is shown inline, not saved to disk. | Must | Built from the in-memory `results`, not from a JSON file. |
| FR-10 | Markdown before each table/figure explains **how to read it** (e.g. "a recovered/true ratio far from 1.0 whose CI excludes 1.0 means the parameter is displaced beyond what pooling can resolve"; "the span is a generator *target*, so compare the realised span with its run-to-run spread"). Prose must **not** state which parameters are or are not protected in this run, nor quote any measured number. | Must | Neutral prose — cannot go stale. |
| FR-11 | A closing markdown cell: results describe this generator, this reference and these seeds; re-run on your own reference before relying on a configuration; no formal privacy guarantee is claimed; pointers to `docs/theory/perturbation.rst`, `scripts/measure_topology_recovery.py` and `powergrid_synth.privacy.recovery`. | Must | |
| FR-12 | Notebook is committed **with executed outputs** (tables and figure visible on GitHub). | Must | Execute once with default settings before committing. |
| FR-13 | Title cell + short intro stating what the notebook reproduces and its expected runtime (≈2 min). Matches the heading style of existing `examples/transmission/*.ipynb` (no Colab badge, since there is no Colab twin). | Should | |

---

## 6. Assumptions & Constraints

- **Assumption:** `synthesize` is deterministic for fixed `seed` and a fixed
  perturbation `seed` on the same machine and dependency versions (`uv.lock`).
  A spot check during spec writing (one grid, strengths 0 and 1.0) ran fine at
  ≈1 s per grid; full determinism is verified by AC-02.
- **Assumption:** the `perturbation_report` attached to each graph is not needed
  by the study; the notebook may ignore it.
- **Constraint:** only public API from `powergrid_synth` (`synthesize`,
  `pandapower_to_nx`, `extract_topology_params_from_graph`,
  `powergrid_synth.privacy.recovery.*`) plus `pandapower`, `networkx`, `numpy`,
  `pandas`, `matplotlib`, and the stdlib. All already in the project environment.
- **Constraint:** runs inside the repo's `.venv` (`uv`-managed); the optional
  `opf` extra is not required (the "opf extra not installed" warning is benign).
- **Constraint:** nothing is written into the repository at run time.

---

## 8. Open Questions

| # | Question | Owner | Due |
|---|----------|-------|-----|
| 1 | If AC-02 reveals non-determinism (numbers differ from the script's JSON), is the acceptable fix to tolerance-compare, or must the root cause be found? Default: report the discrepancy to the owner, do not loosen the check silently. | Implementer → Paul | During implementation |

---

## 9. Verification

### 9.1 Acceptance Criteria

- **AC-01 (FR-01..FR-13):** **Given** a clean checkout with the project
  environment installed, **when** running
  `uv run jupyter nbconvert --to notebook --execute examples/transmission/non_reverse_engineerability.ipynb --output <tmp>`,
  **then** it completes with no errors in under 5 minutes and the output
  contains the three tables and the 3-panel figure.
- **AC-02 (FR-04..FR-07):** **Given** default settings, **when** the notebook's
  `results` dict is compared with the JSON from
  `uv run python scripts/measure_topology_recovery.py --output <tmp>/script.json`,
  **then** `true_node_counts`, `true_spans`, and for every strength every
  `node_count[level].{mean,ci_lo,ci_hi,true}`, `degrees_by_level.ks_distance`
  and `diameters_by_level[level].{mean,stdev,true}` are equal (float
  comparison with `math.isclose(rel_tol=1e-12)`; integer levels compared after
  normalising JSON string keys to `str`).
- **AC-03 (FR-06):** **Given** any generated graph from the pool, **when**
  `measure_spans_by_level(graph)` is compared with
  `_measure_spans_by_level(graph)` (in a throwaway check, not in the notebook),
  **then** the lists are equal.
- **AC-04 (FR-09):** **Given** the executed notebook, **when** viewing the
  figure, **then** it has three panels with the titles, axes labels, reference
  lines and colours of `scripts/make_recovery_figure.py`.
- **AC-05 (FR-10, FR-11):** **Given** the markdown cells, **when** reviewed,
  **then** no cell quotes a measured value or states that a particular
  parameter is/isn't protected on this run; the closing caveat is present.
- **AC-06 (FR-05, constraints):** **Given** a run, **when** checking
  `git status`, **then** no new files appear in the repository besides the
  notebook itself.
- **AC-07 (FR-02, FR-05):** **Given** the notebook source, **when** grepping,
  **then** there are no imports from `scripts`, no `sys.path` edits and no
  import of `_measure_spans_by_level`.

### 9.2 Test Scenarios

| Scenario | Input / State | Expected Result | Covers |
|----------|--------------|-----------------|--------|
| Happy path | Default settings, execute notebook | Runs clean, tables + figure rendered | FR-01..FR-13 |
| Script parity | Default settings; run script with defaults | All numbers identical | FR-04..FR-07 |
| Baseline config | `strength = 0.0` | `build_config` returns `None`; synthesize runs unperturbed | FR-04 |
| Changed settings | Edit settings cell, e.g. `N_GRIDS = 5`, `STRENGTHS = (0.0, 1.0)` | Notebook still runs; tables/figure adapt to the new strengths | FR-01, FR-08, FR-09 |
| Span edge case | Level with < 2 nodes in a generated graph | Span 0 for that level, no exception | FR-06 |
| Single-grid pool | `N_GRIDS = 1` | Span stdev 0.0; node-count CI collapses to the mean; no exception | FR-07 |

### 9.3 Definition of Done

- [ ] All Must requirements implemented
- [ ] AC-01 … AC-07 passing (AC-02 and AC-03 checked once, result reported in the commit/PR message)
- [ ] Notebook committed with executed outputs
- [ ] No changes outside `examples/transmission/non_reverse_engineerability.ipynb`
- [ ] Reviewed by Paul Bannmüller

---

## 11. Revision History

| Version | Date | Author | Summary of changes |
|---------|------|--------|-------------------|
| 0.1     | 2026-09-25 | — | Initial draft |

---

## 12. Implementation Handoff

> This section is the single source of truth for the implementation agent.
> Every decision needed to start coding is captured here.

**Language & runtime:** Python ≥ 3.10 in the repo's `uv`-managed `.venv`; Jupyter notebook (nbformat 4, kernel `python3`).
**Execution model:** Synchronous, sequential. 4 strengths × 30 grids ≈ 120 `synthesize` calls at ≈1 s each.
**Entry point:** `examples/transmission/non_reverse_engineerability.ipynb`, executed top to bottom.
**Code location:** New file `examples/transmission/non_reverse_engineerability.ipynb`. No other files change.
**Existing interfaces to respect:**
- `powergrid_synth.transmission.synthesize.synthesize(*, mode, reference_case, seed, perturbation_config, output_dir, output_name, export_formats) -> nx.Graph`
- `powergrid_synth.core.data_format_converter.pandapower_to_nx(net) -> nx.Graph`
- `powergrid_synth.core.input_extractor.extract_topology_params_from_graph(graph) -> dict` (keys used: `degrees_by_level`, `diameters_by_level`)
- `powergrid_synth.privacy.recovery.recover_node_count(graphs, k) -> {level: {mean, ci_lo, ci_hi, counts}}`
- `powergrid_synth.privacy.recovery.recover_degree_dist_full(graphs, true_degrees_by_level) -> float`
- Reference implementation to mirror: `scripts/measure_topology_recovery.py` (`build_config`, `generate_pool`, `measure`) and `scripts/make_recovery_figure.py` (figure layout, colours `TRUE_COLOUR="#B44C43"`, `ESTIMATE_COLOUR="#2A5C8A"`, `LEVEL_COLOURS=("#1F3B57", "#2A5C8A", "#7BA3C7", "#B8CCE0")`, `figsize=(12.5, 3.6)`).
**Library constraints:** Only `powergrid_synth` public API + `pandapower`, `networkx`, `numpy`, `pandas`, `matplotlib`, stdlib. No new dependencies. No imports from `scripts/`, no private `_`-prefixed imports.
**Test framework:** None added. Verification is `jupyter nbconvert --execute` + a one-off parity check against the script's JSON (AC-02, AC-03), done outside the notebook.
**Style notes:** Research-code style: small, named functions with docstrings (`build_config`, `generate_pool`, `measure_spans_by_level`, `measure`, `plot_recovery`); descriptive variable names; comment density matching `scripts/measure_topology_recovery.py`. Markdown cells are short and neutral.

**Suggested cell outline:**
1. Title + intro (what is reproduced, runtime ≈2 min)
2. Threat model and batch design (markdown)
3. Imports
4. Settings cell (FR-01)
5. Reference grid: load, extract, show true buses/spans (FR-02)
6. `build_config`, `generate_pool` (FR-04, FR-05)
7. `measure_spans_by_level`, `measure` (FR-06, FR-07)
8. Run the study loop over `STRENGTHS` → `results`
9. How-to-read + table: buses per level (FR-08a, FR-10)
10. How-to-read + table: degree KS (FR-08b)
11. How-to-read + table: spans (FR-08c)
12. How-to-read + recovery figure (FR-09)
13. Caveats and pointers (FR-11)

**Requirement priority order for implementation:**
1. FR-01 — settings cell
2. FR-02 — reference load + true parameters
3. FR-04 / FR-05 — config and pool generation
4. FR-06 / FR-07 — estimators and `results` schema
5. AC-02 / AC-03 — parity check against the script before writing prose
6. FR-08 / FR-09 — tables and figure
7. FR-03 / FR-10 / FR-11 / FR-13 — markdown
8. FR-12 — execute and commit with outputs

**Known gotchas / non-obvious decisions:**
- The perturbation seed is **fixed per batch** (`BATCH_SEED = 4242` for every grid); only the synthesiser seed varies (`seed=grid_index`). Using fresh perturbation entropy per grid would invalidate the study.
- Strength `0.0` means **no config at all** (`perturbation_config=None`), not a config with strength 0.
- The script's JSON has string keys (`"0.5"`, level `"0"`), while the in-memory dict uses `str(strength)` for strengths and `int` for levels. Normalise keys before comparing (AC-02).
- Level indices come from the node attribute `voltage_level`; `recover_node_count` takes `k = len(true_params["degrees_by_level"])`.
- The synthesiser prints a lot, so wrap each call in `contextlib.redirect_stdout(io.StringIO())`. The "opf extra not installed" warning goes to stderr/logging and is harmless.
- `export_formats=()` still needs a valid `output_dir`. Use a `tempfile.TemporaryDirectory()` so nothing lands in the repo.
- The span panel uses the level with the **largest true span**, not a fixed level.

**What the implementation must NOT do:**
- Must not add pool-size curves, seed-spread analyses, per-level KS or other parameters.
- Must not quote measured numbers or draw protection conclusions in markdown.
- Must not modify `powergrid_synth/**`, `scripts/**` or `docs/**`, or add a Colab notebook.
- Must not import from `scripts/` or use `_measure_spans_by_level`.
- Must not write figures or JSON into the repository.
