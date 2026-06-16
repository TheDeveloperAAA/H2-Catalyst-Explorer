#!/usr/bin/env python3
"""
================================================================================
 train_photo_grouped.py  --  HONEST grouped retrain of the photo screening model
================================================================================
Fixes the v1 bug: the deployed classifiers used a RANDOM stratified split, which
leaks the same material between train and test and inflates ROC-AUC. The exec
summary told Prof. Dutta the screen was validated "on materials never seen in
training," so this makes that literally true: GroupShuffleSplit by material.

Also folds in the improved curated band gaps (data/photocatalysts_curated.csv).
Trains on the on-disk enriched table (no re-pull). Reports train-vs-test so the
bias-variance gap is visible. Saves nothing unless --save is passed.
================================================================================
"""
import os, re, sys, json, pickle, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBClassifier
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
import chem_knowledge as ck
from paths import MODELS_DIR, DATA_DIR

EP = ElementProperty.from_preset("magpie"); L = EP.feature_labels()
def mg(f):
    try: return EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]","",str(f))))
    except Exception: return [np.nan]*len(L)

# improved band gaps from the curated reliable library
lib = pd.read_csv(os.path.join(DATA_DIR, "photocatalysts_curated.csv"))
GAP = dict(zip(lib.material.astype(str), lib.band_gap_eV))

df = pd.read_csv(os.path.join(MODELS_DIR, "photo_enriched_table.csv"))
df = df[(df.activity_value > 0) & (df.activity_value < 1e7)].copy().reset_index(drop=True)
df["material"] = df["material"].astype(str)
df["bandgap_eV"] = df.apply(lambda r: GAP.get(r["material"], r["bandgap_eV"]), axis=1)

# featurize each unique material once
feat_map = {m: mg(m) for m in df.material.unique()}
F = pd.DataFrame([feat_map[m] for m in df.material], columns=L); F = F.fillna(F.mean())
N = df[["bandgap_eV","scavenger_strength","wavelength_nm","light_power_W","irradiation_time_h"]].copy()
for c in N.columns:
    N[c] = pd.to_numeric(N[c], errors="coerce"); N[c] = N[c].fillna(N[c].median())
oh  = OneHotEncoder(handle_unknown="ignore", sparse_output=True); se = oh.fit_transform(df[["sacrificial_agent"]].astype(str))
ohc = OneHotEncoder(handle_unknown="ignore", sparse_output=True); ce = ohc.fit_transform(df[["has_cocatalyst"]].astype(str))
X = hstack([csr_matrix(F.values), csr_matrix(N.values), se, ce]).tocsr()

q = df.activity_value.quantile([.25,.5,.75]).values
def tier(v): return 0 if v<q[0] else 1 if v<q[1] else 2 if v<q[2] else 3
ytier = df.activity_value.apply(tier).values
ybin  = (df.activity_value >= q[1]).astype(int).values
groups = df.material.values

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
tr, te = next(gss.split(X, ytier, groups))
print(f"rows={len(df)}  train={len(tr)} test={len(te)}  unseen-material test groups="
      f"{len(set(groups[te]) - set(groups[tr]))}/{len(set(groups[te]))}")

TIER_NAMES = ["low","moderate","high","exceptional"]
# Hyperparameters at the bias-variance optimum found by 4-fold grouped CV
# (depth=3, reg_lambda=10, min_child=12 gave best honest CV AUC with the
# smallest train-test gap; deeper/looser settings only overfit, never raised
# the honest ceiling ~0.64).
PARAMS = dict(n_estimators=500, max_depth=3, learning_rate=0.03, subsample=0.8,
              colsample_bytree=0.7, reg_lambda=10.0, min_child_weight=12,
              n_jobs=4, random_state=42)

m4 = XGBClassifier(**PARAMS, eval_metric="mlogloss", num_class=4, objective="multi:softprob")
m4.fit(X[tr], ytier[tr])
acc4_tr = accuracy_score(ytier[tr], m4.predict(X[tr]))
acc4 = accuracy_score(ytier[te], m4.predict(X[te]))
f14  = f1_score(ytier[te], m4.predict(X[te]), average="macro")

mb = XGBClassifier(**PARAMS, eval_metric="logloss")
mb.fit(X[tr], ybin[tr])
auc_tr = roc_auc_score(ybin[tr], mb.predict_proba(X[tr])[:,1])
prb = mb.predict_proba(X[te])[:,1]
accb = accuracy_score(ybin[te], mb.predict(X[te])); f1b = f1_score(ybin[te], mb.predict(X[te]))
auc  = roc_auc_score(ybin[te], prb)

print("\nHONEST grouped validation (test = materials never seen in training):")
print(f"  4-tier : test acc={acc4:.3f}  macroF1={f14:.3f}   (train acc={acc4_tr:.3f}; random=0.25)")
print(f"  binary : test acc={accb:.3f}  F1={f1b:.3f}  ROC-AUC={auc:.3f}   (train AUC={auc_tr:.3f}; random=0.5)")
print(f"  bias-variance gap (binary AUC train-test): {auc_tr-auc:.3f}")
print(f"  [v1 random-split inflated numbers were: tier acc 0.40, ROC-AUC 0.72]")

if "--save" in sys.argv:
    m4.get_booster().save_model(os.path.join(MODELS_DIR, "model_photo_tier.json"))
    mb.get_booster().save_model(os.path.join(MODELS_DIR, "model_photo_binary.json"))
    with open(os.path.join(MODELS_DIR, "encoders_photo_clf.pkl"), "wb") as f:
        pickle.dump({"ohe_scav":oh,"ohe_coc":ohc,"magpie_labels":L,
                     "magpie_means":F.mean().to_dict(),
                     "num_cols":["bandgap_eV","scav","wavelength_nm","light_power_W","irradiation_time_h"],
                     "tier_thresholds":[float(x) for x in q],"tier_names":TIER_NAMES,
                     "median_gap":float(df.bandgap_eV.median()),
                     "cond_medians":{c:float(pd.to_numeric(df[c],errors="coerce").median())
                                     for c in ["wavelength_nm","light_power_W","irradiation_time_h"]}}, f)
    metrics = {"validation":"GroupShuffleSplit by material (honest, unseen materials)",
               "tier_thresholds_umol_h_g":[float(x) for x in q], "tier_names":TIER_NAMES,
               "n_rows":int(len(df)),
               "tier_model":{"accuracy":round(acc4,3),"macro_f1":round(f14,3),"random_baseline":0.25},
               "binary_model":{"accuracy":round(accb,3),"f1":round(f1b,3),"roc_auc":round(auc,3),
                               "random_baseline":0.5,"threshold_umol_h_g":float(q[1])}}
    with open(os.path.join(MODELS_DIR, "photo_classifier_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("\nSAVED honest grouped models + metrics.")
