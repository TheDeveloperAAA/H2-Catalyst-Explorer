#!/usr/bin/env python3
"""
================================================================================
 train_models.py  --  Train both H2 catalyst models and save portable artifacts
================================================================================
Produces the ENGINE: two trained XGBoost models + everything needed to predict
on brand-new materials, saved as portable files his PhD students can run forever
with no server and no internet (after a one-time feature cache).

MODELS
  A. Electrocatalysis  -> predicts H* adsorption / reaction energy (eV).
     Target physics: |dG_H| near 0 = optimal HER catalyst (Sabatier principle).
  B. Photocatalysis    -> predicts log10(H2 evolution rate, umol/h/g).
     Enriched with experimental band gaps + reaction conditions + scavenger.

KEY ENGINEERING DECISIONS (the things that make it trustworthy)
  * Electro: train on H* ONLY, with site descriptor, for a clean HER signal.
  * Photo : canonicalize names, anchor experimental band gaps for showcase
            materials, encode scavenger strength ordinally.
  * Both  : log/robust targets, grouped validation, honest metrics, and a
            saved feature pipeline so new predictions are reproducible.

OUTPUTS (to /mnt/user-data/outputs/models/)
  model_electro.json, model_photo.json        (XGBoost boosters)
  encoders_electro.pkl, encoders_photo.pkl     (fitted encoders + columns)
  training_metrics.json                         (honest performance audit)
  electro_predictions.csv, photo_predictions.csv (test-set actuals vs preds)
"""

import os, re, json, warnings, pickle
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBRegressor

from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty

import chem_knowledge as ck

OUT = "/mnt/user-data/outputs/models"
os.makedirs(OUT, exist_ok=True)
metrics = {}

EP = ElementProperty.from_preset("magpie")
EP_LABELS = EP.feature_labels()

def magpie(formula):
    try:
        c = Composition(re.sub(r"[^A-Za-z0-9().]", "", str(formula)))
        return EP.featurize(c)
    except Exception:
        return [np.nan] * len(EP_LABELS)

print("=" * 70)
print("TRAINING H2 CATALYST MODELS")
print("=" * 70)

# ====================================================================== #
#  MODEL A : ELECTROCATALYSIS  (H* reaction energy, eV)
# ====================================================================== #
print("\n[MODEL A] Electrocatalysis -- HER (H* adsorption energy)")
ea = pd.read_csv("/mnt/user-data/outputs/electrocatalysis_clean.csv")

# Clean HER signal: H*-only reactions (the canonical HER descriptor)
her = ea[ea["adsorbate"] == "H*"].copy()
# physical band; drop reference-mismatch extremes
lo, hi = her.reaction_energy_eV.quantile([0.02, 0.98])
her = her[her.reaction_energy_eV.between(lo, hi)].reset_index(drop=True)
print(f"  H*-only HER rows: {len(her):,}  (energy clipped to [{lo:.2f}, {hi:.2f}] eV)")

# Features: composition (magpie) + facet + site descriptor
feat_e = pd.DataFrame(her["surface_composition"].apply(magpie).tolist(),
                      columns=EP_LABELS)
feat_e = feat_e.fillna(feat_e.mean())

ohe_facet = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
facet_enc = ohe_facet.fit_transform(her[["facet"]].astype(str))
ohe_site = OneHotEncoder(handle_unknown="ignore", sparse_output=True, max_categories=30)
site_enc = ohe_site.fit_transform(her[["site_descriptor"]].astype(str).fillna("unknown"))

Xe = hstack([csr_matrix(feat_e.values), facet_enc, site_enc]).tocsr()
ye = her["reaction_energy_eV"].values

# Group by surface composition so we test generalization to unseen materials
groups = her["surface_composition"].astype(str).values
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tr_idx, te_idx = next(gss.split(Xe, ye, groups))
Xtr, Xte, ytr, yte = Xe[tr_idx], Xe[te_idx], ye[tr_idx], ye[te_idx]

model_e = XGBRegressor(n_estimators=700, max_depth=6, learning_rate=0.03,
                       subsample=0.85, colsample_bytree=0.85,
                       reg_lambda=1.5, n_jobs=4, random_state=42)
model_e.fit(Xtr, ytr)
pe = model_e.predict(Xte)

r2_e = r2_score(yte, pe)
mae_e = mean_absolute_error(yte, pe)
rmse_e = mean_squared_error(yte, pe) ** 0.5
print(f"  R2={r2_e:.3f}  MAE={mae_e:.3f} eV  RMSE={rmse_e:.3f} eV  (grouped split)")
metrics["electrocatalysis"] = {
    "target": "H* reaction energy (eV)", "n_rows": int(len(her)),
    "R2": round(r2_e, 3), "MAE_eV": round(mae_e, 3), "RMSE_eV": round(rmse_e, 3),
    "validation": "GroupShuffleSplit by surface composition (unseen-material test)",
}

# Save artifacts
model_e.get_booster().save_model(f"{OUT}/model_electro.json")
with open(f"{OUT}/encoders_electro.pkl", "wb") as f:
    pickle.dump({"ohe_facet": ohe_facet, "ohe_site": ohe_site,
                 "magpie_labels": EP_LABELS,
                 "magpie_means": feat_e.mean().to_dict()}, f)
pd.DataFrame({"actual_eV": yte, "predicted_eV": pe,
              "surface": her.iloc[te_idx]["surface_composition"].values,
              "facet": her.iloc[te_idx]["facet"].values}
             ).to_csv(f"{OUT}/electro_predictions.csv", index=False)

# Feature importance (for the Justify pillar)
imp_e = model_e.feature_importances_
ncomp = len(EP_LABELS)
top_e = sorted(zip(EP_LABELS, imp_e[:ncomp]), key=lambda x: -x[1])[:8]
metrics["electrocatalysis"]["top_features"] = [{"feature": f, "importance": round(float(i), 4)} for f, i in top_e]
print("  Top compositional drivers:", ", ".join(f for f, _ in top_e[:4]))

# ====================================================================== #
#  MODEL B : PHOTOCATALYSIS  (log10 H2 rate, umol/h/g)
# ====================================================================== #
print("\n[MODEL B] Photocatalysis -- H2 evolution rate (band-gap enriched)")
pc = pd.read_csv("/mnt/user-data/outputs/photocatalysis_clean.csv")
mr = pc[(pc.activity_basis == "umol_h-1_g-1") &
        (pc.activity_value > 0) & (pc.activity_value < 1e7)].copy()

# (1) canonicalize names + reunite fragmented duplicates
mr["material"] = mr["photocatalyst"].apply(ck.canonicalize_name)
mr = mr[mr["material"].notna()].reset_index(drop=True)

# (2) experimental band gap: curated anchor first, else NaN -> median impute
mr["bandgap_eV"] = mr["material"].apply(ck.experimental_gap)
gap_coverage = mr["bandgap_eV"].notna().mean()
print(f"  Experimental band-gap coverage (curated): {gap_coverage*100:.0f}% of rows")
median_gap = mr["bandgap_eV"].median()
mr["bandgap_eV"] = mr["bandgap_eV"].fillna(median_gap)
mr["bandgap_known"] = mr["material"].apply(lambda m: ck.experimental_gap(m) is not None)

# (3) scavenger strength ordinal
mr["scavenger_strength"] = mr["sacrificial_agent"].map(ck.SCAVENGER_STRENGTH).fillna(1)

# (4) numeric conditions
for col in ["wavelength_nm", "light_power_W", "irradiation_time_h"]:
    mr[col] = pd.to_numeric(mr[col], errors="coerce")
mr["wavelength_nm"] = mr["wavelength_nm"].fillna(mr["wavelength_nm"].median())
mr["light_power_W"] = mr["light_power_W"].fillna(mr["light_power_W"].median())
mr["irradiation_time_h"] = mr["irradiation_time_h"].fillna(mr["irradiation_time_h"].median())

mr["logH2"] = np.log10(mr["activity_value"])

# Features: composition(magpie) + bandgap + conditions + categoricals
feat_p = pd.DataFrame(mr["material"].apply(magpie).tolist(), columns=EP_LABELS)
feat_p = feat_p.fillna(feat_p.mean())
num_p = mr[["bandgap_eV", "scavenger_strength", "wavelength_nm",
            "light_power_W", "irradiation_time_h"]].copy()
ohe_scav = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
scav_enc = ohe_scav.fit_transform(mr[["sacrificial_agent"]].astype(str))
ohe_coc = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
coc_enc = ohe_coc.fit_transform(mr[["has_cocatalyst"]].astype(str))

Xp = hstack([csr_matrix(feat_p.values), csr_matrix(num_p.values),
             scav_enc, coc_enc]).tocsr()
yp = mr["logH2"].values

# group by material so we test on unseen catalysts
gp = mr["material"].astype(str).values
gss2 = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tri, tei = next(gss2.split(Xp, yp, gp))
Xtr2, Xte2, ytr2, yte2 = Xp[tri], Xp[tei], yp[tri], yp[tei]

model_p = XGBRegressor(n_estimators=600, max_depth=5, learning_rate=0.03,
                       subsample=0.85, colsample_bytree=0.8,
                       reg_lambda=2.0, n_jobs=4, random_state=42)
model_p.fit(Xtr2, ytr2)
pp = model_p.predict(Xte2)

r2_p = r2_score(yte2, pp)
mae_p = mean_absolute_error(yte2, pp)
# back-transform MAE to a "typical fold error" the chemist understands
fold_err = 10 ** mae_p
print(f"  R2={r2_p:.3f} (log scale)  MAE={mae_p:.3f} log-units  "
      f"= ~{fold_err:.1f}x typical error  (grouped split)")
metrics["photocatalysis"] = {
    "target": "log10(H2 rate, umol/h/g)", "n_rows": int(len(mr)),
    "R2_log": round(r2_p, 3), "MAE_log": round(mae_p, 3),
    "typical_fold_error": round(fold_err, 2),
    "bandgap_coverage_pct": round(gap_coverage * 100, 1),
    "validation": "GroupShuffleSplit by material (unseen-catalyst test)",
}

model_p.get_booster().save_model(f"{OUT}/model_photo.json")
with open(f"{OUT}/encoders_photo.pkl", "wb") as f:
    pickle.dump({"ohe_scav": ohe_scav, "ohe_coc": ohe_coc,
                 "magpie_labels": EP_LABELS,
                 "magpie_means": feat_p.mean().to_dict(),
                 "num_cols": ["bandgap_eV", "scavenger_strength", "wavelength_nm",
                              "light_power_W", "irradiation_time_h"],
                 "median_gap": float(median_gap),
                 "cond_medians": {
                     "wavelength_nm": float(mr["wavelength_nm"].median()),
                     "light_power_W": float(mr["light_power_W"].median()),
                     "irradiation_time_h": float(mr["irradiation_time_h"].median())}}, f)
pd.DataFrame({"material": mr.iloc[tei]["material"].values,
              "actual_log": yte2, "predicted_log": pp,
              "actual_rate": 10 ** yte2, "predicted_rate": 10 ** pp
              }).to_csv(f"{OUT}/photo_predictions.csv", index=False)

ncomp = len(EP_LABELS)
imp_p = model_p.feature_importances_
# map the numeric-feature importances (they sit right after the magpie block)
num_names = ["band gap (eV)", "scavenger strength", "wavelength (nm)",
             "light power (W)", "irradiation time (h)"]
num_imp = list(zip(num_names, imp_p[ncomp:ncomp + 5]))
top_comp_p = sorted(zip(EP_LABELS, imp_p[:ncomp]), key=lambda x: -x[1])[:5]
metrics["photocatalysis"]["top_condition_features"] = [
    {"feature": n, "importance": round(float(i), 4)} for n, i in
    sorted(num_imp, key=lambda x: -x[1])]
metrics["photocatalysis"]["top_composition_features"] = [
    {"feature": f, "importance": round(float(i), 4)} for f, i in top_comp_p]
print("  Condition drivers:", ", ".join(f"{n}({i:.3f})" for n, i in
      sorted(num_imp, key=lambda x: -x[1])))

# also persist the cleaned, enriched modelling table for the dashboard
keep = ["material", "bandgap_eV", "bandgap_known", "sacrificial_agent",
        "scavenger_strength", "has_cocatalyst", "wavelength_nm",
        "light_power_W", "irradiation_time_h", "activity_value", "logH2",
        "source_paper"]
mr[keep].to_csv(f"{OUT}/photo_enriched_table.csv", index=False)

with open(f"{OUT}/training_metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print("\n" + "=" * 70)
print("DONE. Artifacts saved to", OUT)
print("=" * 70)
print(json.dumps(metrics, indent=2))
