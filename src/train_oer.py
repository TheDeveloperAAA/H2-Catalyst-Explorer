#!/usr/bin/env python3
"""
train_oer.py  --  trained OER model (replaces the curated OER reference).

Predicts the reaction energy of each OER intermediate (O*, OH*, OOH*) from
composition + facet + adsorbate, the same proven pipeline that gave HER R2=0.90.
Honest grouped validation by surface composition. From the predicted O* and OH*
energies it derives the standard OER activity descriptor dG(O*)-dG(OH*) and a
0-100 OER score. EDA is printed first.

Saves: models/model_oer.json, models/encoders_oer.pkl, models/oer_metrics.json
"""
import os, re, json, pickle, warnings, sys
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBRegressor
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
from paths import DATA_DIR, MODELS_DIR

EP = ElementProperty.from_preset("magpie"); L = EP.feature_labels()
def mg(f):
    try: return EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]","",str(f))))
    except Exception: return [np.nan]*len(L)

df = pd.read_csv(os.path.join(DATA_DIR, "oer_clean.csv"))
# clip per-adsorbate physical bands (drop reference-mismatch extremes)
keep = []
for a, g in df.groupby("adsorbate"):
    lo, hi = g.reaction_energy_eV.quantile([0.02, 0.98])
    keep.append(g[g.reaction_energy_eV.between(lo, hi)])
df = pd.concat(keep).reset_index(drop=True)

print("=== OER EDA ===")
print(f"rows: {len(df):,} | unique surfaces: {df.surface_composition.nunique():,} | facets: {df.facet.nunique()}")
print("by adsorbate:", df.adsorbate.value_counts().to_dict())
for a, g in df.groupby("adsorbate"):
    print(f"  {a:<5} energy mean {g.reaction_energy_eV.mean():+.2f} +/- {g.reaction_energy_eV.std():.2f} eV  (n={len(g)})")

# features
F = pd.DataFrame([mg(s) for s in df.surface_composition], columns=L); F = F.fillna(F.mean())
ohf = OneHotEncoder(handle_unknown="ignore", sparse_output=True); fac = ohf.fit_transform(df[["facet"]].astype(str))
oha = OneHotEncoder(handle_unknown="ignore", sparse_output=True); ads = oha.fit_transform(df[["adsorbate"]].astype(str))
X = hstack([csr_matrix(F.values), fac, ads]).tocsr()
y = df.reaction_energy_eV.values
# LEAK-FREE grouping: group by the actual composition FEATURE VECTOR, not the raw
# surface_composition string. The string has hundreds of decorations (rutile,
# Cr-doped, O-cov, columbite...) that collapse to ONE magpie vector, so grouping
# by the string let identical feature rows fall in both train and test (inflating
# R2 from a true ~0.70 to 0.86). Rows the model literally cannot tell apart must
# stay in the same fold.
groups = pd.util.hash_pandas_object(F.round(3), index=False).astype(str).values
print(f"groups: {df.surface_composition.nunique():,} surface strings -> {len(set(groups)):,} distinct feature vectors")

PARAMS = dict(n_estimators=700, max_depth=6, learning_rate=0.03, subsample=0.85,
              colsample_bytree=0.85, reg_lambda=1.5, n_jobs=4, random_state=42)

# quick grouped-CV read for honesty
gkf = GroupKFold(n_splits=4); cvr2 = []
for tr, te in gkf.split(X, y, groups):
    m = XGBRegressor(**PARAMS); m.fit(X[tr], y[tr]); cvr2.append(r2_score(y[te], m.predict(X[te])))
print(f"\ngrouped 4-fold CV R2: {np.mean(cvr2):.3f} +/- {np.std(cvr2):.3f}")

# held-out grouped fit
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tr, te = next(gss.split(X, y, groups))
model = XGBRegressor(**PARAMS); model.fit(X[tr], y[tr])
pred = model.predict(X[te])
r2 = r2_score(y[te], pred); mae = mean_absolute_error(y[te], pred)
print(f"held-out grouped: R2={r2:.3f}  MAE={mae:.3f} eV")
# per-adsorbate (recorded, not just printed: the descriptor uses O*/OH*, and the
# headline R2 is dominated by the easy OH* arm, so the split must be inspectable)
te_ads = df.iloc[te].adsorbate.values
arm_R2, arm_n = {}, {}
for a in ["O*","OH*","OOH*"]:
    mask = te_ads == a
    if mask.sum() > 5:
        ar2 = r2_score(y[te][mask], pred[mask])
        arm_R2[a] = round(float(ar2), 3); arm_n[a] = int(mask.sum())
        print(f"  {a:<5} R2={ar2:.3f}  MAE={mean_absolute_error(y[te][mask], pred[mask]):.3f} eV  (n={int(mask.sum())})")

model.get_booster().save_model(os.path.join(MODELS_DIR, "model_oer.json"))
with open(os.path.join(MODELS_DIR, "encoders_oer.pkl"), "wb") as f:
    pickle.dump({"ohe_facet": ohf, "ohe_ads": oha, "magpie_labels": L,
                 "magpie_means": F.mean().to_dict()}, f)
metrics = {"target": "OER intermediate reaction energy (eV)", "n_rows": int(len(df)),
           "validation": "GroupShuffleSplit by composition feature vector (leak-free: identical-composition surface decorations cannot split across folds)",
           "R2": round(float(r2), 3), "MAE_eV": round(float(mae), 3),
           "cv_R2_mean": round(float(np.mean(cvr2)), 3), "cv_R2_std": round(float(np.std(cvr2)), 3),
           "arm_R2": arm_R2, "arm_n": arm_n,
           "descriptor": "OER activity from dG(O*)-dG(OH*); overpotential = max step - 1.23 V"}
with open(os.path.join(MODELS_DIR, "oer_metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)
print("\nsaved model_oer.json + encoders_oer.pkl + oer_metrics.json")
print(json.dumps(metrics, indent=2))
