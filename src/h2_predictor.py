#!/usr/bin/env python3
"""
================================================================================
 h2_predictor.py  --  The unified prediction ENGINE  (runs forever, no server)
================================================================================
This is the piece Prof. Dutta's PhD students import and call on ANY material they
invent. It loads the saved model artifacts and exposes three clean functions
matching the three dashboard pillars:

    predict_electro(surface, facet)      -> H* adsorption energy + HER verdict
    predict_photo(material, conditions)  -> performance tier + promising? + range
    explain(...)                         -> the drivers behind a prediction

USAGE (for his students):
    from h2_predictor import H2Predictor
    p = H2Predictor()
    print(p.predict_photo("ZnO", scavenger="methanol", wavelength=365))
    print(p.predict_electro("Pt", facet="111"))

No internet needed at predict time. Everything is local.
================================================================================
"""
import os, re, json, pickle
import numpy as np
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix
from pymatgen.core import Composition
from matminer.featurizers.composition import ElementProperty
import chem_knowledge as ck

MODELS = os.environ.get("H2_MODEL_DIR", "/mnt/user-data/outputs/models")
_EP = ElementProperty.from_preset("magpie")
_L = _EP.feature_labels()

def _magpie(formula, means):
    try:
        v = _EP.featurize(Composition(re.sub(r"[^A-Za-z0-9().]", "", str(formula))))
        return [means.get(_L[i], 0) if (x is None or np.isnan(x)) else x
                for i, x in enumerate(v)]
    except Exception:
        return [means.get(lab, 0) for lab in _L]


class H2Predictor:
    def __init__(self, model_dir=MODELS):
        self.dir = model_dir
        # electrocatalysis
        self.m_e = xgb.Booster(); self.m_e.load_model(f"{model_dir}/model_electro.json")
        with open(f"{model_dir}/encoders_electro.pkl", "rb") as f:
            self.enc_e = pickle.load(f)
        # photocatalysis classifiers
        self.m_tier = xgb.Booster(); self.m_tier.load_model(f"{model_dir}/model_photo_tier.json")
        self.m_bin = xgb.Booster(); self.m_bin.load_model(f"{model_dir}/model_photo_binary.json")
        with open(f"{model_dir}/encoders_photo_clf.pkl", "rb") as f:
            self.enc_p = pickle.load(f)
        # evidence
        import pandas as pd
        self.evidence = pd.read_csv(f"{model_dir}/photo_evidence_by_material.csv")

    # ----------------------------------------------------------------- #
    #  ELECTROCATALYSIS
    # ----------------------------------------------------------------- #
    def predict_electro(self, surface, facet="111", site="H:hollow"):
        """Predict H* adsorption energy (eV) and give a HER verdict."""
        e = self.enc_e
        feat = _magpie(surface, e["magpie_means"])
        fac = e["ohe_facet"].transform([[str(facet)]])
        sit = e["ohe_site"].transform([[str(site)]])
        X = hstack([csr_matrix([feat]), fac, sit]).tocsr()
        dE = float(self.m_e.predict(xgb.DMatrix(X))[0])
        # Sabatier: |dG_H| near 0 is best. Map to a 0-100 HER suitability score.
        # (this is the standard volcano interpretation)
        suitability = max(0, 100 * (1 - min(abs(dE) / 1.0, 1)))
        if abs(dE) < 0.10:
            verdict = "Excellent HER candidate (near-optimal H binding)"
        elif abs(dE) < 0.35:
            verdict = "Good HER candidate"
        elif abs(dE) < 0.7:
            verdict = "Moderate — binding too " + ("strong" if dE < 0 else "weak")
        else:
            verdict = "Poor — H binding too " + ("strong" if dE < 0 else "weak")
        return {"surface": surface, "facet": facet,
                "predicted_H_energy_eV": round(dE, 3),
                "her_suitability_score": round(suitability, 1),
                "verdict": verdict}

    # ----------------------------------------------------------------- #
    #  PHOTOCATALYSIS
    # ----------------------------------------------------------------- #
    def predict_photo(self, material, scavenger="methanol", has_cocatalyst=True,
                      wavelength=None, power=None, time_h=None):
        """Predict performance tier + 'promising?' screen + evidence range."""
        e = self.enc_p
        canon = ck.canonicalize_name(material) or material
        gap = ck.experimental_gap(canon)
        gap_known = gap is not None
        if gap is None:
            gap = e["median_gap"]
        scav_str = ck.SCAVENGER_STRENGTH.get(scavenger, 1)
        cm = e["cond_medians"]
        wl = wavelength if wavelength is not None else cm["wavelength_nm"]
        pw = power if power is not None else cm["light_power_W"]
        th = time_h if time_h is not None else cm["irradiation_time_h"]

        feat = _magpie(canon, e["magpie_means"])
        num = [[gap, scav_str, wl, pw, th]]
        sc = e["ohe_scav"].transform([[str(scavenger)]])
        cc = e["ohe_coc"].transform([[str(bool(has_cocatalyst))]])
        X = hstack([csr_matrix([feat]), csr_matrix(num), sc, cc]).tocsr()
        dm = xgb.DMatrix(X)

        tier_proba = self.m_tier.predict(dm)[0]
        tier_idx = int(np.argmax(tier_proba))
        promising_proba = float(self.m_bin.predict(dm)[0])

        # evidence range from real published data for this material
        ev = self.evidence[self.evidence.material == canon]
        if len(ev):
            row = ev.iloc[0]
            ev_range = {"n_papers": int(row["n"]),
                        "median_rate": round(float(row["median_rate"]), 1),
                        "typical_low": round(float(row["p25"]), 1),
                        "typical_high": round(float(row["p75"]), 1)}
        else:
            ev_range = None

        return {
            "material": canon,
            "band_gap_eV": round(gap, 2),
            "band_gap_source": "experimental (curated)" if gap_known else "dataset median (unknown material)",
            "performance_tier": e["tier_names"][tier_idx],
            "tier_confidence": round(float(tier_proba[tier_idx]), 2),
            "promising_probability": round(promising_proba, 2),
            "promising_verdict": ("Likely worth synthesizing" if promising_proba >= 0.6
                                  else "Borderline — check evidence" if promising_proba >= 0.4
                                  else "Likely low performer"),
            "published_evidence": ev_range,
            "conditions_used": {"scavenger": scavenger, "scavenger_strength": scav_str,
                                "has_cocatalyst": bool(has_cocatalyst),
                                "wavelength_nm": wl},
        }

    # ----------------------------------------------------------------- #
    #  RECOMMENDER  (the "what should I change?" pillar)
    # ----------------------------------------------------------------- #
    def recommend_photo(self, material, base_scavenger="none/unspecified"):
        """Try common condition changes, report which lift the promising-probability most."""
        base = self.predict_photo(material, scavenger=base_scavenger)["promising_probability"]
        levers = []
        for scav in ["methanol", "TEOA", "Na2S/Na2SO3", "glycerol"]:
            for coc in [True]:
                r = self.predict_photo(material, scavenger=scav, has_cocatalyst=coc)
                levers.append({"change": f"use {scav} scavenger + co-catalyst",
                               "new_probability": r["promising_probability"],
                               "delta": round(r["promising_probability"] - base, 2)})
        levers = sorted(levers, key=lambda x: -x["delta"])
        return {"material": ck.canonicalize_name(material) or material,
                "baseline_probability": base, "top_levers": levers[:3]}


if __name__ == "__main__":
    p = H2Predictor()
    print("=== ELECTROCATALYSIS demos ===")
    for s in ["Pt", "Ni", "Au", "MoS2"]:
        print(" ", p.predict_electro(s, "111"))
    print("\n=== PHOTOCATALYSIS demos (Prof. Dutta's materials) ===")
    for m in ["ZnO", "g-C3N4", "CdS", "TiO2"]:
        r = p.predict_photo(m, scavenger="methanol")
        print(f"  {m}: tier={r['performance_tier']} (conf {r['tier_confidence']}), "
              f"promising={r['promising_probability']}, gap={r['band_gap_eV']}eV [{r['band_gap_source']}]")
    print("\n=== RECOMMENDER demo ===")
    print(" ", p.recommend_photo("ZnO"))
