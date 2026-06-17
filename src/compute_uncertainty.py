#!/usr/bin/env python3
"""
compute_uncertainty.py  --  honest uncertainty + calibration.

  - HER / OER: split-conformal prediction interval (the 90th-percentile absolute
    residual fit on a CALIBRATION fold) WITH an empirical coverage check on a
    disjoint TEST fold, so "90%" is a measured property, not an assertion.
  - OER uses a LEAK-FREE grouping (by composition feature vector, not the raw
    surface string), matching train_oer.py.
  - OER descriptor band dG(O*)-dG(OH*): a difference of two energies, so its band
    is wider than the per-energy band. Pooled across several grouped folds for a
    stable quantile (a single split gives n~22 and swings 1.4-3.1 across seeds).
  - Photocatalysis: isotonic calibration of the binary "promising" probability,
    fit ONLY on the held-out rows the booster never trained on (out-of-sample),
    so the calibration is honest rather than optimistic.

Output: data/uncertainty.json
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

def conformal_band(resid, groups, rng):
    """90th-pct abs-residual on a calibration half + measured coverage on the
    disjoint test half. Splitting by GROUP keeps a material wholly on one side."""
    resid = np.asarray(resid); groups = np.asarray(groups)
    gu = np.array(sorted(set(groups))); rng.shuffle(gu)
    cal_g = set(gu[: max(1, len(gu) // 2)])
    cal = np.array([gg in cal_g for gg in groups])
    band = float(np.quantile(resid[cal], 0.90))
    cov = float(np.mean(resid[~cal] <= band)) if (~cal).sum() else float("nan")
    return round(band, 2), round(cov, 3), int((~cal).sum())

out = {}
rng = np.random.default_rng(0)

# ---- HER conformal from the saved held-out test set, with coverage check ----
her = pd.read_csv(os.path.join(MODELS_DIR, "electro_predictions.csv"))
hres = (her["actual_eV"] - her["predicted_eV"]).abs().values
hg = her["surface"].astype(str).values
out["her_pm"], out["her_coverage"], out["her_cov_n"] = conformal_band(hres, hg, rng)

# ---- OER: leak-free grouping, conformal band + coverage, pooled descriptor band ----
oer = pd.read_csv(os.path.join(DATA_DIR, "oer_clean.csv"))
keep = []
for a, gdf in oer.groupby("adsorbate"):
    lo, hi = gdf.reaction_energy_eV.quantile([0.02, 0.98]); keep.append(gdf[gdf.reaction_energy_eV.between(lo, hi)])
oer = pd.concat(keep).reset_index(drop=True)
F = pd.DataFrame([mg(s) for s in oer.surface_composition], columns=L).fillna(0)
ohf = OneHotEncoder(handle_unknown="ignore", sparse_output=True); fa = ohf.fit_transform(oer[["facet"]].astype(str))
oha = OneHotEncoder(handle_unknown="ignore", sparse_output=True); ad = oha.fit_transform(oer[["adsorbate"]].astype(str))
X = hstack([csr_matrix(F.values), fa, ad]).tocsr(); y = oer.reaction_energy_eV.values
# group by the composition feature vector (same leak-free key as train_oer.py)
g = pd.util.hash_pandas_object(F.round(3), index=False).astype(str).values
from xgboost import XGBRegressor
PARAMS = dict(n_estimators=700, max_depth=6, learning_rate=0.03, subsample=0.85,
              colsample_bytree=0.85, reg_lambda=1.5, n_jobs=4, random_state=42)
tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=1).split(X, y, g))
m = XGBRegressor(**PARAMS); m.fit(X[tr], y[tr])
pred = m.predict(X[te])
out["oer_pm"], out["oer_coverage"], out["oer_cov_n"] = conformal_band(np.abs(y[te] - pred), g[te], rng)

# descriptor band: pool the (O*-OH*) residual over EVERY held-out fold of a grouped
# 5-fold CV, so the quantile rests on many surfaces, not a single split's ~22.
dres = []
gkf = GroupKFold(n_splits=5)
for tri, tei in gkf.split(X, y, g):
    mf = XGBRegressor(**PARAMS); mf.fit(X[tri], y[tri])
    td = oer.iloc[tei].copy(); td["pred"] = mf.predict(X[tei])
    for _, gg in td.groupby("surface_composition"):
        o = gg[gg.adsorbate == "O*"]; oh = gg[gg.adsorbate == "OH*"]
        if len(o) and len(oh):
            dres.append(abs((o.reaction_energy_eV.mean() - oh.reaction_energy_eV.mean())
                            - (o.pred.mean() - oh.pred.mean())))
out["oer_desc_pm"] = round(float(np.quantile(dres, 0.90)), 2)
out["oer_desc_n"] = len(dres)

# ---- Photo isotonic calibration, OUT-OF-SAMPLE (held-out rows only) ----
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
# reproduce the EXACT training split (GSS material-grouped, rs=42); the model was
# fit on `tr`, so only `te` rows are genuinely unseen -> calibrate on those alone.
ptr, pte = next(GroupShuffleSplit(1, test_size=0.2, random_state=42).split(Xp, yb, gp))
mb = xgb.Booster(); mb.load_model(os.path.join(MODELS_DIR, "model_photo_binary.json"))
raw_te = mb.predict(xgb.DMatrix(Xp[pte]))
iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98).fit(raw_te, yb[pte])
xs = np.linspace(0, 1, 21); ys = iso.predict(xs)
out["photo_calib"] = {"x": [round(float(v), 3) for v in xs], "y": [round(float(v), 3) for v in ys],
                      "out_of_sample": True, "n_calib": int(len(pte))}

json.dump(out, open(os.path.join(DATA_DIR, "uncertainty.json"), "w"))
print(f"HER +/- {out['her_pm']} eV (coverage {out['her_coverage']} on n={out['her_cov_n']})")
print(f"OER energy +/- {out['oer_pm']} eV (coverage {out['oer_coverage']} on n={out['oer_cov_n']})")
print(f"OER descriptor +/- {out['oer_desc_pm']} eV (pooled over {out['oer_desc_n']} surfaces, 5 folds)")
print(f"photo calibration: out-of-sample on {out['photo_calib']['n_calib']} held-out rows")
print("wrote", os.path.join(DATA_DIR, "uncertainty.json"))
