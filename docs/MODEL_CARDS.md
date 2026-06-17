# Model cards

Three trained models plus a curated/heuristic overlay layer. Every prediction in
the dashboard is labelled `trained`, `evidence-backed`, or `curated` so users can
see which applies.

---

## Model A : HER (electrocatalysis)

- **Task.** Regress the H* reaction/adsorption energy (eV); by the Sabatier
  principle |dG_H| near 0 is optimal.
- **Algorithm.** XGBoost gradient-boosted trees.
- **Training data.** Catalysis-Hub MamunHighT2019 (Mamun et al., Sci Data 2019,
  CC-BY): ~4,150 H*-only rows after filtering, bimetallic/metallic alloys of 37
  metals, 111/101 facets. DFT: Quantum Espresso, BEEF-vdW / RPBE.
- **Features.** 132 Magpie compositional descriptors + facet + adsorption site.
- **Validation.** GroupShuffleSplit by surface composition (unseen-material test).
- **Performance.** R2 = 0.90, MAE = 0.15 eV. Conformal 90% interval ± 0.36 eV.
- **Intended use.** Rank metal/alloy surfaces for HER suitability.
- **Limits.** Trained on one high-throughput alloy study; non-alloy chemistries
  (oxides, sulfides such as MoS2) are flagged `extrapolated` and are out of domain.
  Vacuum/implicit DFT, electrolyte-blind. **Composition-level:** the features are
  compositional, so the model does not resolve facet or adsorption site (it returns
  one value per composition; the "(111)" framing is nominal). The target is the DFT
  H* binding energy (dE), not the zero-point/entropy-corrected free energy
  (dG ~ dE + 0.24 eV); the volcano is read on that same dE scale.
- **License.** Data CC-BY 4.0. Model: this repo.

## Model B : Photocatalysis screen

- **Task.** Classify H2-evolution performance: 4-tier and a binary "promising"
  screen. Exact-rate regression is deliberately avoided (caps at R2 ~0.14).
- **Algorithm.** XGBoost classification.
- **Training data.** Isazawa & Cole 2023 text-mined photocatalysis DB (Sci Data,
  Figshare 10.6084/m9.figshare.21932211, CC-BY), ~7,290 H2 rows after cleaning,
  names canonicalised, units normalised. Note: text-mining (authors' F1 ~48%),
  so the corpus is noisy.
- **Features.** Magpie + experimental band gap + scavenger strength + light
  conditions.
- **Validation.** GroupShuffleSplit by material (unseen-catalyst test).
- **Performance.** Binary ROC-AUC 0.65, accuracy 0.60; 4-tier accuracy 0.35
  (random 0.25). Probability isotonic-calibrated **out-of-sample**: the isotonic map
  is fit only on the ~1,010 held-out rows the booster never trained on, so the
  calibration is honest rather than in-sample optimistic.
- **Calibration is not accuracy.** Calibration only makes the displayed % mean what
  it says (of materials shown ~30%, about 30% really are promising). It does NOT
  improve the model's ability to separate good from bad: the grouped ROC-AUC stays
  ~0.65. Read the % as a calibrated probability, not as confidence the model is
  right. The SHAP drivers explain the *raw* model; because the calibration map is
  monotonic, each driver's up/down direction carries over even though the displayed
  magnitude is post-calibration.
- **Intended use.** Prioritise which materials are worth synthesising; always read
  alongside the published-evidence range shown per material.
- **Limits.** Composition-level only: blind to polymorph, facet, nanostructure and
  surface area, which dominate real rates. A weak discriminator by design; honest
  not precise. Dropdown is evidence-gated (>=3 papers + a real band gap).
- **License.** Data CC-BY 4.0. Model: this repo.

## Model C : OER (electrocatalysis)

- **Task.** Regress O*, OH*, OOH* reaction energies, then form the OER activity
  descriptor dG(O*) - dG(OH*) (optimum ~1.6 eV).
- **Algorithm.** XGBoost regression.
- **Training data.** Catalysis-Hub O/OH/OOH reactions (CC-BY), 2,828 rows / 1,016
  surfaces. Note: a sampled pull (page-capped); OOH* is thin (n=203).
- **Features.** Magpie + facet + adsorbate.
- **Validation.** GroupShuffleSplit / GroupKFold by the **composition feature vector**,
  NOT the raw surface string. This is a correctness fix: the surface strings carry
  hundreds of decorations (`IrO2-rutile`, `Cr-doped-IrO2`, `IrO2-O-cov`...) that
  collapse to one Magpie vector, so grouping by the string let identical feature
  rows fall in both train and test. 1,025 surface strings reduce to 632 distinct
  feature vectors; grouping by the vector is leak-free.
- **Performance (honest, leak-free).** Grouped-CV R2 = **0.64 ± 0.26** (single held-out
  split 0.32; the spread is large because skill varies sharply by composition family).
  Per-arm held-out R2: OH* 0.54, O* 0.03, OOH* strongly negative. **An earlier R2 0.86
  was almost entirely leakage** from the string grouping above. Per-energy conformal
  90% interval ± 1.26 eV, with **measured coverage 0.88** on a disjoint test fold.
- **This model is deliberately treated as WEAK.** Because the O* and OOH* arms barely
  predict on unseen compositions, the trained descriptor is a low-confidence
  cross-check, not the primary signal. The UI leads with the curated literature
  overpotential wherever one exists and flags any case where the model verdict
  disagrees with it.
- **Descriptor uncertainty is larger than per-energy.** The descriptor dG(O*) - dG(OH*)
  is a *difference* of two predicted energies, so its band exceeds the per-energy band.
  Pooled over five grouped folds (91 surfaces) it is **± 3.4 eV (90%)** - wide enough
  that the descriptor is for rough ranking only, never an absolute overpotential.
- **Confidence split.** Of the 45 OER catalysts shown, 25 carry a literature
  overpotential (representative, @10 mA/cm2, primary signal) and 20 are **model-only**
  (no literature anchor), flagged lower-confidence in the UI.
- **Intended use.** Rank genuine OER catalysts, led by literature overpotential; the
  descriptor adds a weak directional cross-check.
- **Limits.** Applicability domain restricted to redox-transition-metal oxides /
  perovskites / pyrochlores; main-group oxides (ZnO, Ag3PO4) are excluded. The
  metal/alloy-heavy training set underrates noble oxides (RuO2, IrO2), which is
  exactly why literature is primary and the model is shown only for transparency.
- **License.** Data CC-BY 4.0. Model: this repo.

## Curated / heuristic overlays (NOT trained)

Flagged in the UI as `curated`. Electrolyte (alkaline/acidic) guidance, defect and
heterostructure effect-sizes, band-edge positions (literature where available, else
Mulliken estimate, flagged), solar absorption, cost / toxicity / earth-abundance,
and stability. These are literature-based rules or element heuristics, never model
outputs.

**Provenance honesty.** The curated band edges (40 CB/VB pairs) and OER overpotentials
(25 values) are **representative literature values, not individually cited per entry**.
They are typical, textbook-consistent numbers for each material, suitable for ranking
and screening, but a specific entry should be confirmed against a primary source before
it is quoted in a paper. The UI labels them "representative" and never presents an
author-supplied value as a measured citation. Band-edge entries that are a Mulliken
estimate (E_CB = chi - 4.5 - 0.5*Eg) rather than literature are flagged "(est)", and
their water-splitting verdict is shown as indicative ("Likely (est)"), not confirmed.

## Band-gap provenance (127 materials)

True source is recorded per material (the builder no longer relabels its own literature
values as curated): roughly 62 literature, 34 hand-curated, 30 measured (expt_gap,
Zhuo-Brgoch, matched by reduced formula), 1 reconciled. The exact live counts are in
`data/photocatalysts_curated.csv` (`gap_source` column) and surfaced in the UI as
"Experimental" vs "Estimated".

## Known limitations (whole system)

- **No external/temporal validation yet.** The text-mined corpora do not carry a clean
  per-row publication year, so a leak-free "train on pre-2020, test on newer papers"
  split is not yet possible. Grouped-by-material CV is the current honesty floor; a
  temporal hold-out is the next validation upgrade and is tracked as future work.
- The 40 curated band edges and 25 OER overpotentials are representative, not
  per-value cited (see above).
- The single largest accuracy lever, morphology / surface-area features and the
  lab's own experimental data, is not yet included.
- **Bundle size.** The 3D front-end ships a ~1.3 MB committed JS bundle (three.js +
  react-three-fiber). This is a deliberate trade: the tool stays a zero-server static
  site that "opens in any browser, no setup", at the cost of a larger first load. The
  lightweight `classic.html` remains available for low-bandwidth use.
- **Fully offline (verified).** Fonts (Fraunces, Spline Sans, Inter) are self-hosted
  as ~175 KB of variable woff2 under `fonts/`; the previous Google-Fonts `@import` was
  removed, so neither front-end makes any network request. `deploy.sh` asserts no
  `googleapis`/`gstatic` reference survives in either front-end or the built bundle,
  and that `classic.html`'s inlined DATA deep-equals `dashboard_data.json` (so the two
  front-ends cannot drift in numbers or honesty framing).
