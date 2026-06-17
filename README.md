# H₂ Catalyst Explorer

**Machine-learning screening of photocatalysts and electrocatalysts for green-hydrogen generation.**

A predictive tool that estimates how effective a material is at producing hydrogen - across both the photocatalytic (sunlight-driven) and electrocatalytic (electrolysis) routes - and explains *why* each prediction is trustworthy, grounding every answer in published experimental evidence.

🔗 **[Open the live dashboard →](https://thedeveloperaaa.github.io/H2-Catalyst-Explorer/)**

> Built during a Quantitative AI/ML Research Internship for Prof. R. K. Dutta, Department of Chemistry, IIT Roorkee.

---

## What it does

Six sections, all in one browser file:

- **Photocatalysis** : choose from 127 reliable photocatalysts (each a real material with a real experimental band gap) and conditions; get a performance tier and a "worth synthesizing?" probability, with a confidence badge and the real published evidence range.
- **Electrocatalysis** : both half-reactions of electrolysis. HER (hydrogen) is a trained model on DFT H-binding energies; OER (oxygen) is a curated reference of literature overpotentials. An alkaline / acidic electrolyte guide flags which regime each catalyst suits.
- **Defects & Heterostructures** : toggle oxygen / metal vacancies, doping, surface modification, and type-II heterojunctions to see their curated, literature-based effect.
- **Recommend** : which practical change (scavenger, co-catalyst) most improves a material's hydrogen output.
- **Litmus test** : model predictions placed next to known chemistry on canonical materials, including the honest misses (Pt mid-pack for HER).
- **Why trust it** : the model's honest grouped accuracy and the properties that drive each prediction.

Every output is labelled by confidence: `trained` model, `evidence-backed`, or `curated` guidance. The dashboard runs entirely in the browser, no server, no internet, no expiry. A companion Python engine (`src/h2_predictor.py`) runs the same models on any new material.

---

## Results

| Model | Metric | Notes |
|-------|--------|-------|
| **Electrocatalysis HER** (trained) | **R² = 0.90**, MAE = 0.15 eV | Validated on *unseen materials* (grouped split). Error is near the precision of the underlying DFT calculations. |
| **Photocatalysis** (screening, trained) | **ROC-AUC = 0.65**, ~60% accuracy | Honest grouped validation (test on materials never seen in training); 4-tier at 0.35 (vs 0.25 random). The earlier 0.72 came from a leaky random split and was corrected. |
| **Electrocatalysis OER** (trained) | **grouped CV R² = 0.77**, ± 1.81 eV | Trained on Catalysis-Hub O/OH/OOH energies (not OC22). Activity descriptor dG(O*)-dG(OH*); domain-restricted to genuine OER catalysts. Literature overpotential shown as primary for the ~25 well-known ones. |

Full provenance, metrics, intended use, and limits per model are in [docs/MODEL_CARDS.md](docs/MODEL_CARDS.md). All regression predictions carry conformal ± bands and the photo probability is isotonic-calibrated.

**The electrocatalysis model independently rediscovered known chemistry:** with no hints, it ranks MoS₂ as the top HER catalyst, and honestly places Pt mid-pack (its (111) surface binds H slightly too strongly), matching what the field knows. The Litmus tab shows this directly.

**On photocatalysis, the model deliberately does not predict an exact rate.** The same material appears in the literature with 100× different rates depending on nanostructure and synthesis, details the source papers rarely record. Rather than emit false precision, the tool classifies performance tiers, screens promising candidates, and always shows the real published spread. For an experimentalist, an honest range beats a confident wrong number.

---

## How it was built

**Data**
- **Catalysis-Hub** - ~41k DFT reaction/adsorption energies (electrocatalysis), pulled via GraphQL API.
- **Isazawa & Cole 2023 photocatalysis database** - ~12.6k text-mined experimental H₂-evolution records.
- **Materials Project** - structural/compositional descriptors.

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
  h2_predictor.py       ← prediction engine - run on any new material
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
