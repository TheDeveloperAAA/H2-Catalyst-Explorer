# H₂ Catalyst Explorer

**Machine-learning screening of photocatalysts and electrocatalysts for green-hydrogen generation.**

A predictive tool that estimates how effective a material is at producing hydrogen — across both the photocatalytic (sunlight-driven) and electrocatalytic (electrolysis) routes — and explains *why* each prediction is trustworthy, grounding every answer in published experimental evidence.

🔗 **[Open the live dashboard →](https://thedeveloperaaa.github.io/H2-Catalyst-Explorer/)**

> Built during a Quantitative AI/ML Research Internship for Prof. R. K. Dutta, Department of Chemistry, IIT Roorkee.

---

## What it does

The dashboard has three pillars:

- **Predict** — choose a catalyst and reaction conditions; get a performance tier (low → exceptional) and a "worth synthesizing?" probability, with confidence.
- **Recommend** — see which practical changes (hole scavenger, co-catalyst) most improve a material's hydrogen output.
- **Justify** — every prediction shows the properties that drove it, the model's honest accuracy, and the real published range of hydrogen rates for similar materials.

The dashboard runs entirely in the browser — no server, no internet, no expiry. A companion Python engine (`src/h2_predictor.py`) runs the same models on *any* new material.

---

## Results

| Model | Metric | Notes |
|-------|--------|-------|
| **Electrocatalysis** (HER) | **R² = 0.90**, MAE = 0.15 eV | Validated on *unseen materials* (grouped split). Error is near the precision of the underlying DFT calculations. |
| **Photocatalysis** (screening) | **ROC-AUC = 0.72**, ~65% accuracy | Binary "promising vs. not" screen; 4-tier classifier at 0.40 accuracy (vs 0.25 random). |

**The electrocatalysis model independently rediscovered known chemistry** — with no hints, it ranks MoS₂ and Pt among the best HER catalysts, exactly the materials the field celebrates.

**On photocatalysis, the model deliberately does not predict an exact rate.** The same material appears in the literature with 100× different rates depending on nanostructure and synthesis — details the source papers rarely record. Rather than emit false precision, the tool classifies performance tiers, screens promising candidates, and always shows the real published spread. For an experimentalist, an honest range beats a confident wrong number.

---

## How it was built

**Data**
- **Catalysis-Hub** — ~41k DFT reaction/adsorption energies (electrocatalysis), pulled via GraphQL API.
- **Isazawa & Cole 2023 photocatalysis database** — ~12.6k text-mined experimental H₂-evolution records.
- **Materials Project** — structural/compositional descriptors.

**Method**
- Materials → numerical descriptors via **Matminer Magpie** (elemental properties) + experimental band gap + reaction conditions.
- **XGBoost** gradient-boosted trees for both regression (electro) and classification (photo).
- Honest **grouped validation** (test on materials never seen in training).

**A key trust decision:** raw DFT band gaps are severely underestimated (DFT puts ZnO at 0.7 eV; the real value is 3.3 eV). The showcase materials are anchored to curated **experimental** band gaps, so predictions stay credible on materials chemists know well.

---

## Repository structure

```
index.html              ← the interactive dashboard (GitHub Pages serves this)
models/                 ← trained XGBoost artifacts + encoders + evidence tables
src/
  h2_predictor.py       ← prediction engine — run on any new material
  chem_knowledge.py     ← experimental band gaps, name normalization (trust layer)
  train_models.py       ← trains the electrocatalysis + photo regressors
  train_photo_classifier.py ← trains the photo tier/binary classifiers
  build_*_dataset.py    ← data ingestion + cleaning pipelines
docs/
  EXECUTIVE_SUMMARY.md  ← non-technical overview
  README_TECHNICAL.md   ← full technical documentation
```

---

## Run the engine on a new material

```bash
pip install -r requirements.txt
```

```python
from src.h2_predictor import H2Predictor
p = H2Predictor(model_dir="models")

p.predict_photo("ZnO", scavenger="methanol", has_cocatalyst=True)
p.predict_electro("MoS2", facet="111")
p.recommend_photo("CdS")
```

---

## License & attribution

Data: Catalysis-Hub (Winther et al., *Sci Data* 2019); photocatalysis DB (Isazawa & Cole, *Sci Data* 2023, Figshare `10.6084/m9.figshare.21932211`); Materials Project (Jain et al.). Models: XGBoost. Featurization: Matminer.
