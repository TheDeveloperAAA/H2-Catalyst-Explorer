#!/usr/bin/env python3
"""
compute_uncertainty.py  --  honest uncertainty + calibration.

  - HER / OER: split-conformal prediction interval (the 90th-percentile absolute
    residual on a held-out set), so every regression prediction gets a +/- band.
  - Photocatalysis: isotonic calibration of the binary "promising" probability
    on a grouped-by-material hold-out, so the percentage means what it says.

Output: data/uncertainty.json
  { her_pm: <eV>, oer_pm: <eV>, photo_calib: {x:[...], y:[...]} }
"""
import os, re, json, pickle, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import OneHotEncoder
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
import chem_knowledge as ck
from paths import MODELS_DIR, DATA_DIR

EP = ElementProperty.from_preset("magpie"); L = EP.feature_labels()
def mg(f, means=None):
    try:
        v = EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]", "", str(f))))
        if means is None: return [0 if (x is None or (isinstance(x, float) and np.isnan(x))) else x for x in v]
        return [means.get(L[i], 0) if (x is None or (isinstance(x, float) and np.isnan(x))) else x for i, x in enumerate(v)]
    except Exception:
        return [0] * len(L) if means is None else [means.get(l, 0) for l in L]

out = {}

# ---- HER conformal from the saved held-out test set ----
her = pd.read_csv(os.path.join(MODELS_DIR, "electro_predictions.csv"))
res = (her["actual_eV"] - her["predicted_eV"]).abs()
out["her_pm"] = round(float(np.quantile(res, 0.90)), 2)

# ---- OER conformal: grouped split refit ----
oer = pd.read_csv(os.path.join(DATA_DIR, "oer_clean.csv"))
keep = []
for a, g in oer.groupby("adsorbate"):
    lo, hi = g.reaction_energy_eV.quantile([0.02, 0.98]); keep.append(g[g.reaction_energy_eV.between(lo, hi)])
oer = pd.concat(keep).reset_index(drop=True)
F = pd.DataFrame([mg(s) for s in oer.surface_composition], columns=L).fillna(0)
ohf = OneHotEncoder(handle_unknown="ignore", sparse_output=True); fa = ohf.fit_transform(oer[["facet"]].astype(str))
oha = OneHotEncoder(handle_unknown="ignore", sparse_output=True); ad = oha.fit_transform(oer[["adsorbate"]].astype(str))
X = hstack([csr_matrix(F.values), fa, ad]).tocsr(); y = oer.reaction_energy_eV.values
g = oer.surface_composition.astype(str).values
tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=1).split(X, y, g))
from xgboost import XGBRegressor
m = XGBRegressor(n_estimators=700, max_depth=6, learning_rate=0.03, subsample=0.85, colsample_bytree=0.85, reg_lambda=1.5, n_jobs=4, random_state=42)
m.fit(X[tr], y[tr])
pred = m.predict(X[te])
out["oer_pm"] = round(float(np.quantile(np.abs(y[te] - pred), 0.90)), 2)
# descriptor band: residual of (O* - OH*) on test surfaces having BOTH adsorbates
td = oer.iloc[te].copy(); td["pred"] = pred
dres = []
for _, gg in td.groupby("surface_composition"):
    o = gg[gg.adsorbate == "O*"]; oh = gg[gg.adsorbate == "OH*"]
    if len(o) and len(oh):
        dres.append(abs((o.reaction_energy_eV.mean() - oh.reaction_energy_eV.mean()) - (o.pred.mean() - oh.pred.mean())))
out["oer_desc_pm"] = round(float(np.quantile(dres, 0.90)), 2) if len(dres) >= 20 else round(out["oer_pm"] * 2 ** 0.5, 2)

# ---- Photo isotonic calibration on a grouped hold-out ----
with open(os.path.join(MODELS_DIR, "encoders_photo_clf.pkl"), "rb") as f:
    ep = pickle.load(f)
lib = pd.read_csv(os.path.join(DATA_DIR, "photocatalysts_curated.csv"))
GAP = dict(zip(lib.material.astype(str), lib.band_gap_eV))
df = pd.read_csv(os.path.join(MODELS_DIR, "photo_enriched_table.csv"))
df = df[(df.activity_value > 0) & (df.activity_value < 1e7)].copy().reset_index(drop=True)
df["material"] = df["material"].astype(str)
df["bandgap_eV"] = df.apply(lambda r: GAP.get(r["material"], r["bandgap_eV"]), axis=1)
feat_map = {mm: mg(mm, ep["magpie_means"]) for mm in df.material.unique()}
Fp = pd.DataFrame([feat_map[mm] for mm in df.material], columns=L).fillna(0)
N = df[["bandgap_eV", "scavenger_strength", "wavelength_nm", "light_power_W", "irradiation_time_h"]].copy()
for c in N.columns: N[c] = pd.to_numeric(N[c], errors="coerce"); N[c] = N[c].fillna(N[c].median())
se = ep["ohe_scav"].transform(df[["sacrificial_agent"]].astype(str))
ce = ep["ohe_coc"].transform(df[["has_cocatalyst"]].astype(str))
Xp = hstack([csr_matrix(Fp.values), csr_matrix(N.values), se, ce]).tocsr()
q = df.activity_value.quantile([.25, .5, .75]).values
yb = (df.activity_value >= q[1]).astype(int).values
gp = df.material.values
mb = xgb.Booster(); mb.load_model(os.path.join(MODELS_DIR, "model_photo_binary.json"))
# cross-validated isotonic calibration: fit per grouped fold, average the curve
xs = np.linspace(0, 1, 21); ys_folds = []
for _, tei in GroupKFold(n_splits=3).split(Xp, yb, gp):
    raw = mb.predict(xgb.DMatrix(Xp[tei]))
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98).fit(raw, yb[tei])
    ys_folds.append(iso.predict(xs))
ys = np.mean(ys_folds, axis=0)
out["photo_calib"] = {"x": [round(float(v), 3) for v in xs], "y": [round(float(v), 3) for v in ys], "cv_folds": 3}

json.dump(out, open(os.path.join(DATA_DIR, "uncertainty.json"), "w"))
print("HER +/-", out["her_pm"], "eV | OER energy +/-", out["oer_pm"], "eV | OER descriptor +/-", out["oer_desc_pm"], "eV")
print("photo calibration sample (raw -> cal):", list(zip(out["photo_calib"]["x"][::5], out["photo_calib"]["y"][::5])))
print("wrote", os.path.join(DATA_DIR, "uncertainty.json"))
