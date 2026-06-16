#!/usr/bin/env python3
"""
compute_shap.py  --  per-material "why" drivers via exact TreeSHAP.

Uses XGBoost's built-in pred_contribs=True (exact TreeSHAP, no extra dependency)
to explain each prediction: which features pushed the "promising" probability up
or down for that specific material. Closes the original charter's SHAP deliverable.

Outputs data/shap.json: { photo: {mat: [{feature, impact, dir}]}, her: {surf: [...]} }
"""
import os, re, json, pickle, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
import chem_knowledge as ck
from paths import MODELS_DIR, DATA_DIR

EP = ElementProperty.from_preset("magpie"); L = EP.feature_labels()
def magpie(formula, means):
    try:
        v = EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]", "", str(formula))))
        return [means.get(L[i], 0) if (x is None or (isinstance(x, float) and np.isnan(x))) else x for i, x in enumerate(v)]
    except Exception:
        return [means.get(lab, 0) for lab in L]

# friendly names for the cryptic Magpie descriptors
PROP = {
    "Column": "periodic group", "Row": "periodic period", "Number": "atomic number",
    "MendeleevNumber": "Mendeleev number", "AtomicWeight": "atomic weight",
    "MeltingT": "melting point", "CovalentRadius": "atomic size",
    "Electronegativity": "electronegativity", "NsValence": "s-electrons",
    "NpValence": "p-electrons", "NdValence": "d-electrons", "NfValence": "f-electrons",
    "NValence": "valence electrons", "NsUnfilled": "s-vacancies", "NpUnfilled": "p-vacancies",
    "NdUnfilled": "d-vacancies", "NfUnfilled": "f-vacancies", "NUnfilled": "electron vacancies",
    "GSvolume_pa": "atomic volume", "GSbandgap": "elemental band gap",
    "GSmagmom": "magnetic moment", "SpaceGroupNumber": "crystal symmetry",
}
def pretty_magpie(label):
    s = label.replace("MagpieData ", "")
    parts = s.split(" ", 1)
    stat = parts[0] if len(parts) > 1 else ""
    prop = parts[1] if len(parts) > 1 else parts[0]
    friendly = PROP.get(prop, prop)
    return friendly if stat in ("", "mean", "mode") else f"{friendly} ({stat})"

def top_drivers(contribs, names, k=4):
    pairs = sorted(zip(names, contribs[:-1]), key=lambda x: -abs(x[1]))
    out = []
    seen = set()
    for nm, val in pairs:
        if abs(val) < 1e-4 or nm in seen:
            continue
        seen.add(nm)
        out.append({"feature": nm, "impact": round(float(val), 3), "dir": "up" if val > 0 else "down"})
        if len(out) >= k:
            break
    return out

# ---------------- PHOTO ----------------
with open(os.path.join(MODELS_DIR, "encoders_photo_clf.pkl"), "rb") as f:
    ep = pickle.load(f)
mb = xgb.Booster(); mb.load_model(os.path.join(MODELS_DIR, "model_photo_binary.json"))
num_names = ["band gap", "scavenger strength", "wavelength", "light power", "irradiation time"]
scav_cats = ["scavenger=" + c for c in ep["ohe_scav"].categories_[0]]
coc_cats = ["co-catalyst=" + c for c in ep["ohe_coc"].categories_[0]]
photo_names = [pretty_magpie(l) for l in L] + num_names + scav_cats + coc_cats

lib = pd.read_csv(os.path.join(DATA_DIR, "photocatalysts_curated.csv"))
cm = ep["cond_medians"]
photo_shap = {}
for mat in lib.material.astype(str):
    gap = ck.experimental_gap(mat)
    gap = gap if gap is not None else ep["median_gap"]
    feat = magpie(mat, ep["magpie_means"])
    num = [[gap, 2, cm["wavelength_nm"], cm["light_power_W"], cm["irradiation_time_h"]]]
    sc = ep["ohe_scav"].transform([["methanol"]])
    cc = ep["ohe_coc"].transform([["True"]])
    X = hstack([csr_matrix([feat]), csr_matrix(num), sc, cc]).tocsr()
    contribs = mb.predict(xgb.DMatrix(X), pred_contribs=True)[0]
    photo_shap[mat] = top_drivers(contribs, photo_names)

# ---------------- ELECTRO HER ----------------
with open(os.path.join(MODELS_DIR, "encoders_electro.pkl"), "rb") as f:
    ee = pickle.load(f)
me = xgb.Booster(); me.load_model(os.path.join(MODELS_DIR, "model_electro.json"))
fac_cats = ["facet=" + c for c in ee["ohe_facet"].categories_[0]]
site_cats = ["site=" + c for c in ee["ohe_site"].categories_[0]]
her_names = [pretty_magpie(l) for l in L] + fac_cats + site_cats

import json as _j
DATA = _j.load(open(os.path.join(MODELS_DIR.replace("models", "data"), "dashboard_data.json")))
her_shap = {}
for surf in DATA["electro"].keys():
    feat = magpie(surf, ee["magpie_means"])
    fa = ee["ohe_facet"].transform([["111"]])
    si = ee["ohe_site"].transform([["H:hollow"]])
    X = hstack([csr_matrix([feat]), fa, si]).tocsr()
    contribs = me.predict(xgb.DMatrix(X), pred_contribs=True)[0]
    her_shap[surf] = top_drivers(contribs, her_names)

out = {"photo": photo_shap, "her": her_shap}
with open(os.path.join(DATA_DIR, "shap.json"), "w") as f:
    json.dump(out, f)
print(f"SHAP drivers: photo {len(photo_shap)} materials, her {len(her_shap)} surfaces")
print("sample CdS:", photo_shap.get("CdS"))
print("sample MoS2 (HER):", her_shap.get("MoS2"))
print("wrote", os.path.join(DATA_DIR, "shap.json"))
