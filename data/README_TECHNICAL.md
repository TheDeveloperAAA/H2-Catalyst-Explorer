# H₂ Catalyst Explorer — Technical README

Predictive screening of photocatalysts and electrocatalysts for hydrogen generation.
Two XGBoost models + a self-contained dashboard + a reusable Python prediction engine.

---

## Repository contents

### The dashboard (what Prof. Dutta opens)
- `H2_Catalyst_Explorer.html` — self-contained interactive dashboard. Opens in any
  browser, no server/internet. Three pillars: Predict, Recommend, Justify. All
  predictions are precomputed and embedded.

### The engine (what PhD students run on new materials)
- `h2_predictor.py` — the `H2Predictor` class: `predict_electro()`,
  `predict_photo()`, `recommend_photo()`. Runs locally on any material.
- `chem_knowledge.py` — curated chemistry: experimental band gaps for showcase
  materials, name normalization, scavenger strengths. **The trust layer.**
- `models/` — trained artifacts:
  - `model_electro.json` — HER reaction-energy regressor (XGBoost booster)
  - `model_photo_tier.json` — 4-class performance-tier classifier
  - `model_photo_binary.json` — "promising?" binary classifier
  - `encoders_*.pkl` — fitted feature encoders + metadata
  - `*_metrics.json` — honest performance audits
  - `photo_evidence_by_material.csv` — real published-rate distributions

### The data pipelines (reproducibility / showcase of method)
- `build_electrocatalysis_dataset.py` — pulls Catalysis-Hub via GraphQL
- `build_photocatalysis_dataset.py` — consolidates the Cole 2023 Figshare DB
- `train_models.py` — trains electro regressor + photo regressor
- `train_photo_classifier.py` — trains the photo tier/binary classifiers
- `electrocatalysis_clean.csv`, `photocatalysis_clean.csv` — cleaned datasets
- `*_quality_report.txt` — data-quality audits

---

## Quick start for PhD students — predict on a new material

```python
from h2_predictor import H2Predictor
p = H2Predictor()

# Photocatalysis: is this material + condition promising?
print(p.predict_photo("ZnO", scavenger="methanol", has_cocatalyst=True))
#  -> performance tier, "promising" probability, experimental band gap,
#     and the real published H2-rate range for that material.

# Electrocatalysis: how good is this surface for HER?
print(p.predict_electro("MoS2", facet="111"))
#  -> predicted H-binding energy (eV) + Sabatier-based HER suitability score.

# Recommend: what change most improves this material?
print(p.recommend_photo("CdS"))
#  -> ranked condition changes by predicted improvement.
```

Works on any material string — the engine featurizes the composition on the fly.
For materials in the curated set, it uses experimental band gaps; for others it
falls back to the dataset median and flags this in `band_gap_source`.

### Environment
```
pip install xgboost scikit-learn matminer pymatgen pandas numpy --break-system-packages
```
First call downloads Magpie elemental-property tables (one-time, needs internet
once); afterwards the engine runs fully offline.

---

## How the models work

### Model A — Electrocatalysis (regression)
- **Target:** H* reaction/adsorption energy (eV), the standard HER descriptor.
  By the Sabatier principle, |ΔG_H| ≈ 0 is optimal.
- **Features:** Magpie compositional descriptors (132) + surface facet + adsorption
  site descriptor.
- **Data:** Catalysis-Hub MamunHighT2019, H*-only reactions, ~4,150 rows after
  filtering to a clean physical band.
- **Validation:** GroupShuffleSplit by surface composition — tests generalization
  to materials never seen in training (the honest, harder test).
- **Performance:** R² = 0.90, MAE = 0.15 eV. (For comparison, prior literature
  reporting R² ≈ 0.98 used random splits, which leak similar surfaces between
  train/test and inflate the score.)

### Model B — Photocatalysis (classification, by design)
- **Why classification, not regression:** exact-rate regression caps at R² ≈ 0.18
  because the true H2 rate depends on nanostructure / morphology / synthesis that
  the source literature does not consistently record. Two papers reporting
  "TiO₂ + methanol + Xe lamp" can differ 100× because of morphology alone. So the
  model predicts what the data *can* support reliably.
- **Targets:** (1) performance tier (quartiles: low/moderate/high/exceptional);
  (2) binary "promising" (top half of the rate distribution).
- **Features:** Magpie descriptors + **experimental band gap** + scavenger strength
  (ordinal) + reaction conditions (wavelength, power, time) + co-catalyst flag.
- **Data:** Cole 2023 photocatalysis DB, H2-evolution records normalized to
  µmol h⁻¹ g⁻¹, names canonicalized, ~7,290 rows.
- **Performance:** 4-tier accuracy 0.40 (vs 0.25 random); binary accuracy 0.65,
  **ROC-AUC 0.72** — a genuinely useful promising-vs-not screen.

### The band-gap correction (the key trust decision)
Raw DFT band gaps from Materials Project are severely underestimated (wurtzite
ZnO: DFT 0.72 eV vs experiment ~3.3 eV). Since band gap is the dominant physical
driver of photocatalytic activity and Prof. Dutta's materials are defined by their
gaps, we anchor the showcase materials to curated **experimental** band gaps in
`chem_knowledge.py`. MP is still used for compositional/structural descriptors,
where DFT is reliable.

---

## Honest limitations
- Photocatalysis predicts *tiers and screening probability*, not exact rates — by
  design, for the reasons above. Always read the predictions alongside the
  published-evidence range the tool shows.
- Coverage is strongest for well-studied materials (g-C₃N₄, TiO₂, CdS, ZnO, …).
  Exotic/novel compositions get composition-similarity-based estimates flagged as
  lower-confidence.
- The dashboard's predictions are precomputed for the showcase materials × the
  condition controls. Truly arbitrary new materials are handled by the Python
  engine, not the static HTML.

## Suggested next steps
1. Fold in the Dutta group's own experimental H2 results to fine-tune Model B on
   the exact material families the lab studies.
2. Add morphology/surface-area features if/when a dataset carrying them is found —
   this is the single biggest lever for improving photocatalysis rate prediction.
3. Optional: deploy the engine as a hosted web app for live arbitrary-material
   prediction (the static dashboard already covers demos and showcase materials).

## Data sources & methods
- **Catalysis-Hub** (Winther et al., *Sci Data* 2019) — electrocatalysis reaction energies, via GraphQL API.
- **Photocatalysis DB** (Isazawa & Cole, *Sci Data* 2023, Figshare 10.6084/m9.figshare.21932211) — text-mined H2-evolution records.
- **Materials Project** (Jain et al.) — structural/compositional descriptors.
- **Models:** XGBoost. **Features:** Matminer Magpie. **Language:** Python.
