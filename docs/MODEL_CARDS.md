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
  (random 0.25). Probability isotonic-calibrated on a grouped hold-out.
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
  R2 0.44. Conformal 90% interval ± 1.81 eV (large: treat with care).
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

## Known limitations (whole system)

- No external/temporal validation yet (e.g. hold out the most recent papers).
- ~65 of 127 band gaps are literature values cross-checked against `expt_gap`
  where they overlap; the rest are author-curated.
- The single largest accuracy lever, morphology / surface-area features and the
  lab's own experimental data, is not yet included.
