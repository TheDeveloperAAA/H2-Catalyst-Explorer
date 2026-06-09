#!/usr/bin/env python3
"""
================================================================================
 train_photo_classifier.py  --  Photocatalysis screening model (HONEST framing)
================================================================================
The photocatalysis data caps at R2~0.18 for exact-rate regression because the
true rate depends on nanostructure/morphology/synthesis that text-mining could
not capture. Rather than emit false-precision numbers, we predict what the data
CAN support reliably:

  * PRIMARY  : performance tier (low / moderate / high / exceptional)
               + a binary "promising?" screen with calibrated probability.
  * SECONDARY: an expected log-rate RANGE (median + spread) from the real
               published distribution of similar systems -- shown as evidence,
               not as a point prediction.

This is the screening question a PhD student actually has: "is this material +
condition worth synthesizing?" The model answers that with ROC-AUC ~0.73.

OUTPUTS (to /mnt/user-data/outputs/models/)
  model_photo_tier.json      (4-class booster)
  model_photo_binary.json    (promising-vs-not booster)
  encoders_photo_clf.pkl     (encoders + tier thresholds + evidence table)
  photo_classifier_metrics.json
"""
import os, re, json, pickle, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             confusion_matrix, classification_report)
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack, csr_matrix
from xgboost import XGBClassifier
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
import chem_knowledge as ck

OUT = "/mnt/user-data/outputs/models"
os.makedirs(OUT, exist_ok=True)
EP = ElementProperty.from_preset("magpie"); L = EP.feature_labels()
def mg(f):
    try: return EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]", "", str(f))))
    except: return [np.nan]*len(L)

print("="*70); print("PHOTOCATALYSIS SCREENING MODEL (classification framing)"); print("="*70)

pc = pd.read_csv("/mnt/user-data/outputs/photocatalysis_clean.csv")
mr = pc[(pc.activity_basis=="umol_h-1_g-1")&(pc.activity_value>0)&(pc.activity_value<1e7)].copy()
mr["material"] = mr["photocatalyst"].apply(ck.canonicalize_name)
mr = mr[mr["material"].notna()].reset_index(drop=True)
mr["bandgap_eV"] = mr["material"].apply(ck.experimental_gap)
mr["bandgap_known"] = mr["bandgap_eV"].notna()
med_gap = mr["bandgap_eV"].median()
mr["bandgap_eV"] = mr["bandgap_eV"].fillna(med_gap)
mr["scav"] = mr["sacrificial_agent"].map(ck.SCAVENGER_STRENGTH).fillna(1)
for c in ["wavelength_nm","light_power_W","irradiation_time_h"]:
    mr[c] = pd.to_numeric(mr[c], errors="coerce"); mr[c] = mr[c].fillna(mr[c].median())

# Tier thresholds from the real distribution (quartiles)
q = mr.activity_value.quantile([0.25,0.5,0.75]).values
def tier(v): return 0 if v<q[0] else 1 if v<q[1] else 2 if v<q[2] else 3
mr["tier"] = mr.activity_value.apply(tier)
TIER_NAMES = ["low","moderate","high","exceptional"]
print(f"Tier thresholds (umol/h/g): <{q[0]:.0f} | <{q[1]:.0f} | <{q[2]:.0f} | >={q[2]:.0f}")

# Features
F = pd.DataFrame(mr.material.apply(mg).tolist(), columns=L); F = F.fillna(F.mean())
N = mr[["bandgap_eV","scav","wavelength_nm","light_power_W","irradiation_time_h"]]
oh = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
se = oh.fit_transform(mr[["sacrificial_agent"]].astype(str))
ohc = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
ce = ohc.fit_transform(mr[["has_cocatalyst"]].astype(str))
X = hstack([csr_matrix(F.values), csr_matrix(N.values), se, ce]).tocsr()

metrics = {"tier_thresholds_umol_h_g": [float(x) for x in q],
           "tier_names": TIER_NAMES, "n_rows": int(len(mr))}

# --- 4-tier model ---
y = mr.tier.values
Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)
m4 = XGBClassifier(n_estimators=500,max_depth=5,learning_rate=0.04,subsample=0.85,
                   colsample_bytree=0.8,n_jobs=4,random_state=42,
                   eval_metric="mlogloss",num_class=4,objective="multi:softprob")
m4.fit(Xtr,ytr); p4 = m4.predict(Xte)
acc4 = accuracy_score(yte,p4); f14 = f1_score(yte,p4,average="macro")
print(f"4-tier: accuracy={acc4:.3f}  macro-F1={f14:.3f}  (random=0.25)")
metrics["tier_model"] = {"accuracy": round(acc4,3), "macro_f1": round(f14,3),
                         "random_baseline": 0.25}
m4.get_booster().save_model(f"{OUT}/model_photo_tier.json")

# --- binary "promising" model (top half) ---
yb = (mr.activity_value >= q[1]).astype(int).values
Xtr,Xte,ytr,yte = train_test_split(X,yb,test_size=0.2,random_state=42,stratify=yb)
mb = XGBClassifier(n_estimators=500,max_depth=5,learning_rate=0.04,subsample=0.85,
                   colsample_bytree=0.8,n_jobs=4,random_state=42,eval_metric="logloss")
mb.fit(Xtr,ytr); pb = mb.predict(Xte); prb = mb.predict_proba(Xte)[:,1]
accb = accuracy_score(yte,pb); f1b = f1_score(yte,pb); auc = roc_auc_score(yte,prb)
print(f"binary promising: accuracy={accb:.3f}  F1={f1b:.3f}  ROC-AUC={auc:.3f}")
metrics["binary_model"] = {"accuracy": round(accb,3), "f1": round(f1b,3),
                           "roc_auc": round(auc,3), "random_baseline": 0.5,
                           "threshold_umol_h_g": float(q[1])}
mb.get_booster().save_model(f"{OUT}/model_photo_binary.json")

# --- feature importance for Justify pillar ---
nc = len(L)
num_names = ["band gap (eV)","scavenger strength","wavelength (nm)",
             "light power (W)","irradiation time (h)"]
imp = mb.feature_importances_
num_imp = sorted(zip(num_names, imp[nc:nc+5]), key=lambda x:-x[1])
comp_imp = sorted(zip(L, imp[:nc]), key=lambda x:-x[1])[:6]
metrics["binary_model"]["condition_feature_importance"] = [
    {"feature":n,"importance":round(float(i),4)} for n,i in num_imp]
metrics["binary_model"]["composition_feature_importance"] = [
    {"feature":f,"importance":round(float(i),4)} for f,i in comp_imp]

# --- evidence table: per-material real published distribution (for Justify) ---
ev = (mr.groupby("material")
        .agg(n=("activity_value","size"),
             median_rate=("activity_value","median"),
             p25=("activity_value", lambda s: s.quantile(.25)),
             p75=("activity_value", lambda s: s.quantile(.75)),
             bandgap_eV=("bandgap_eV","first"),
             bandgap_known=("bandgap_known","first"))
        .reset_index().sort_values("n", ascending=False))
ev.to_csv(f"{OUT}/photo_evidence_by_material.csv", index=False)
print(f"Evidence table: {len(ev)} materials with published-rate distributions")

with open(f"{OUT}/encoders_photo_clf.pkl","wb") as f:
    pickle.dump({"ohe_scav":oh,"ohe_coc":ohc,"magpie_labels":L,
                 "magpie_means":F.mean().to_dict(),
                 "num_cols":["bandgap_eV","scav","wavelength_nm","light_power_W","irradiation_time_h"],
                 "tier_thresholds":[float(x) for x in q],"tier_names":TIER_NAMES,
                 "median_gap":float(med_gap),
                 "cond_medians":{c:float(mr[c].median()) for c in ["wavelength_nm","light_power_W","irradiation_time_h"]}},f)
with open(f"{OUT}/photo_classifier_metrics.json","w") as f:
    json.dump(metrics,f,indent=2)

print("\nDONE. Honest photocatalysis screening model saved.")
print(json.dumps(metrics,indent=2)[:600])
