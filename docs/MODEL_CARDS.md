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
  Vacuum/implicit DFT, electrolyte-blind.
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
  (random 0.25). Probability isotonic-calibrated, averaged over a 3-fold grouped
  cross-validation (not a single split), so the curve is stable.
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
- **Validation.** GroupShuffleSplit by surface composition.
- **Performance.** Grouped CV R2 0.77 (held-out 0.86); OH* arm R2 0.91, OOH* arm
  R2 0.44. Per-energy conformal 90% interval ± 1.81 eV.
- **Descriptor uncertainty is larger than per-energy.** The activity descriptor is a
  *difference* of two predicted energies, dG(O*) - dG(OH*), so its band is wider than
  the ± 1.81 eV per-energy band. Measured directly from paired O*/OH* residuals it is
  ± 2.77 eV (90%). The descriptor is therefore reliable for **ranking**, not for an
  absolute overpotential. The UI shows this ± 2.77 eV band on the descriptor.
- **Confidence split.** Of the 45 OER catalysts shown, 25 carry a literature
  overpotential (anchored, cross-checked by the model) and 20 are **model-only**
  (no literature anchor) and are flagged lower-confidence in the UI.
- **Intended use.** Rank genuine OER catalysts by the activity descriptor.
- **Limits.** Applicability domain restricted to redox-transition-metal oxides /
  perovskites / pyrochlores; main-group oxides (ZnO, Ag3PO4) are excluded. The
  metal/alloy-heavy training set underrates noble oxides (RuO2, IrO2), so for the
  ~25 well-known catalysts the **literature overpotential is shown as primary** and
  the model as a cross-check. Absolute overpotential from the descriptor is an
  estimate (ranking only).
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
