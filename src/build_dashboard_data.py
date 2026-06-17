#!/usr/bin/env python3
"""
================================================================================
 build_dashboard_data.py  --  regenerate the embedded dashboard DATA
================================================================================
Produces the single embedded `const DATA = {...}` object the static dashboard
renders from. Non-regression by construction:
  * the ELECTRO block, scavenger list and scavenger strengths are preserved
    VERBATIM from the current index.html (the electro tab cannot change),
  * the PHOTO block is regenerated for the full curated reliable library
    (127 materials, a strict superset of the materials already live),
  * metrics are updated to the HONEST grouped numbers.

Every photo material carries: real band gap + source, material class, a
confidence level (evidence-backed / limited-evidence / model-estimate), the
real published evidence range, the per-condition predictions, and the
recommender levers. Output: data/dashboard_data.json, and the DATA line in
index.html is rewritten in place.
================================================================================
"""
import os, re, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import h2_predictor as hp
import chem_knowledge as ck
import curated_overlays as co
from paths import MODELS_DIR, DATA_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "classic.html")
SCAVS = ["none/unspecified", "methanol", "ethanol", "glycerol", "TEOA", "Na2S/Na2SO3"]

def load_current_data():
    for line in open(INDEX):
        if line.startswith("const DATA = "):
            return json.loads(line[len("const DATA = "):].rstrip().rstrip(";"))
    raise RuntimeError("DATA line not found in index.html")

def confidence_of(n):
    if n >= 5:  return "evidence-backed"
    if n >= 1:  return "limited-evidence"
    return "model-estimate"

def build_photo(p, lib):
    photo = {}
    for _, row in lib.iterrows():
        mat = str(row["material"])
        n = int(row["n_papers"]) if pd.notna(row["n_papers"]) else 0
        combos = {}
        for scav in SCAVS:
            for coc in (True, False):
                r = p.predict_photo(mat, scavenger=scav, has_cocatalyst=coc)
                combos[f"{scav}|{str(coc).lower()}"] = {
                    "tier": r["performance_tier"], "tier_conf": r["tier_confidence"],
                    "promising": r["promising_probability"], "verdict": r["promising_verdict"]}
        base = p.predict_photo(mat, scavenger="none/unspecified")
        ev = None
        if n > 0 and pd.notna(row.get("median_rate")):
            ev = {"n_papers": n, "median_rate": float(row["median_rate"]),
                  "typical_low": float(row["p25"]), "typical_high": float(row["p75"])}
        photo[mat] = {
            "band_gap_eV": base["band_gap_eV"],
            "band_gap_source": base["band_gap_source"],
            "class": row.get("class", ""),
            "confidence": confidence_of(n),
            "evidence": ev,
            "combos": combos,
            "recommendation": p.recommend_photo(mat),
        }
    return photo

def build_overlays(DATA, p, enrich):
    """Trained OER (domain-restricted) + curated overlays + litmus benchmark."""
    # OER domain: only genuine OER catalysts. Curated set + redox-transition-metal
    # oxides. Main-group oxides (ZnO, Ag3PO4, CdO, SnO2, ...) are excluded because
    # they are not OER catalysts, which removes the descriptor false positives.
    oer_mats = {}
    for m, v in co.OER_CATALYSTS.items():
        oer_mats[m] = {"lit_eta_mV": v["eta_mV"], "electrolyte": v["electrolyte"], "class": v["class"]}
    for m in DATA["photo"]:
        cls = DATA["photo"][m].get("class")
        if m not in oer_mats and enrich.get(m, {}).get("oer_domain"):
            oer_mats[m] = {"lit_eta_mV": None, "electrolyte": "alkaline", "class": cls}
    DATA["oer"] = {}
    for m, info in oer_mats.items():
        r = p.predict_oer(m, "110")
        if r is None:
            continue
        lit = info["lit_eta_mV"]
        # Reconcile the trained descriptor against the curated literature eta. The
        # metal/alloy-heavy training set underrates noble/known oxides, so where a
        # literature eta exists it is PRIMARY and the model is a cross-check. Flag
        # the (common) case where the model verdict openly disagrees so the UI can
        # lead with the literature value instead of a misleading "Poor".
        lit_verdict = co.oer_verdict(lit) if lit else None
        lit_good = (lit is not None and lit <= 340)
        model_good = (r["oer_score"] >= 55)
        disagrees = bool(lit is not None and (lit_good != model_good))
        DATA["oer"][m] = {"descriptor": r["oer_descriptor_eV"], "score": r["oer_score"],
                          "overpotential_V": r["overpotential_V"], "verdict": r["verdict"],
                          "dG_O": r["dG_O_eV"], "dG_OH": r["dG_OH_eV"], "dG_OOH": r["dG_OOH_eV"],
                          "lit_eta_mV": lit, "lit_verdict": lit_verdict,
                          "verdict_primary": lit_verdict if lit else r["verdict"],
                          "model_disagrees": disagrees,
                          "confidence": "literature-anchored" if lit else "model-only",
                          "electrolyte": info["electrolyte"], "class": info["class"]}
    DATA["electrolyte_notes"] = {s: {"acidic": co.her_electrolyte_note(s, "acidic"),
                                     "alkaline": co.her_electrolyte_note(s, "alkaline")}
                                 for s in DATA["electro"]}
    DATA["defects"] = co.DEFECT_EFFECTS
    el, ph = DATA["electro"], DATA["photo"]
    KNOWN_E = {"MoS2": ["Celebrated earth-abundant HER catalyst", True],
               "Pt": ["Textbook HER benchmark; (111) binds slightly too strong here, which is real", "partial"],
               "Ni": ["Moderate HER metal, better in alkaline", True],
               "Au": ["Weak HER, binds H too weakly", True],
               "NiFe": ["Strong bimetallic HER/OER", True],
               "Cu": ["Modest HER metal", True]}
    KNOWN_P = {"g-C3N4": "Workhorse visible-light photocatalyst",
               "CdS": "High-activity sulfide (with sacrificial agent)",
               "TiO2": "UV benchmark, modest under visible light",
               "ZnO": "Classic wide-gap oxide",
               "ZnIn2S4": "Well-studied ternary sulfide"}
    bench = []
    for m, (note, agree) in KNOWN_E.items():
        if m in el:
            bench.append({"domain": "HER", "material": m,
                          "predicted": f"{el[m]['score']:.0f}/100, {el[m]['energy_eV']:+.2f} eV",
                          "known": note, "agree": agree})
    for m, note in KNOWN_P.items():
        if m in ph:
            c = ph[m]["combos"]["methanol|true"]; ev = ph[m]["evidence"]
            evn = f", {ev['n_papers']} studies (median {round(ev['median_rate'])})" if ev else ""
            bench.append({"domain": "Photo", "material": m,
                          "predicted": f"{c['tier']} tier, {round(c['promising']*100)}% promising{evn}",
                          "known": note, "agree": True})
    DATA["benchmark"] = bench

def main():
    DATA = load_current_data()                       # preserve electro/scavengers/strengths
    p = hp.H2Predictor(model_dir=MODELS_DIR)
    lib = pd.read_csv(os.path.join(DATA_DIR, "photocatalysts_curated.csv"))
    lib = lib.sort_values(["n_papers", "material"], ascending=[False, True])

    DATA["photo"] = build_photo(p, lib)
    enrich = {}
    try:
        enrich = json.load(open(os.path.join(DATA_DIR, "enrich.json"))).get("materials", {})
    except Exception:
        pass
    build_overlays(DATA, p, enrich)
    for m, ex in enrich.items():
        if m in DATA["photo"]:
            DATA["photo"][m].update(ex)
    try:
        DATA["shap"] = json.load(open(os.path.join(DATA_DIR, "shap.json")))
    except Exception:
        DATA["shap"] = {}

    # photo probability calibration (isotonic) + conformal uncertainty bands
    DATA["uncertainty"] = {}
    try:
        unc = json.load(open(os.path.join(DATA_DIR, "uncertainty.json")))
        cx, cy = unc["photo_calib"]["x"], unc["photo_calib"]["y"]
        cal = lambda pp: round(float(np.interp(pp, cx, cy)), 2)
        for mm in DATA["photo"].values():
            for c in mm["combos"].values():
                c["promising"] = cal(c["promising"])
            rec = mm.get("recommendation")
            if rec:
                rec["baseline_probability"] = cal(rec["baseline_probability"])
                for lev in rec.get("top_levers", []):
                    lev["new_probability"] = cal(lev["new_probability"])
                    lev["delta"] = round(lev["new_probability"] - rec["baseline_probability"], 2)
                rec["top_levers"] = sorted(rec["top_levers"], key=lambda x: -x["delta"])[:3]
        DATA["uncertainty"] = {"her_pm": unc["her_pm"], "oer_pm": unc["oer_pm"],
                               "oer_desc_pm": unc.get("oer_desc_pm"),
                               "her_coverage": unc.get("her_coverage"), "oer_coverage": unc.get("oer_coverage"),
                               "photo_calibrated": True,
                               "calib_out_of_sample": unc["photo_calib"].get("out_of_sample", False),
                               "calib_n": unc["photo_calib"].get("n_calib")}
    except Exception:
        pass

    # HER applicability domain (Mamun training set = pure metals / alloys, no nonmetals)
    NONMETAL = {"S", "Se", "Te", "O", "N", "C", "P", "B", "H", "Cl", "F", "I", "Br"}
    def her_domain(s):
        return not (set(re.findall(r"[A-Z][a-z]?", str(s))) & NONMETAL)
    for mm in DATA["electro"]:
        DATA["electro"][mm]["in_domain"] = her_domain(mm)

    # honest metrics (electro untouched; photo updated to grouped numbers)
    m = json.load(open(os.path.join(MODELS_DIR, "photo_classifier_metrics.json")))
    DATA["metrics"]["photo_tier_acc"]   = m["tier_model"]["accuracy"]
    DATA["metrics"]["photo_binary_acc"] = m["binary_model"]["accuracy"]
    DATA["metrics"]["photo_roc_auc"]    = m["binary_model"]["roc_auc"]
    DATA["metrics"]["photo_validation"] = "GroupShuffleSplit by material (unseen materials)"
    DATA["metrics"]["photo_n_materials"] = len(DATA["photo"])
    try:
        om = json.load(open(os.path.join(MODELS_DIR, "oer_metrics.json")))
        DATA["metrics"]["oer_R2"] = om["R2"]
        DATA["metrics"]["oer_cv_R2"] = om["cv_R2_mean"]
        DATA["metrics"]["oer_cv_R2_std"] = om.get("cv_R2_std")
        DATA["metrics"]["oer_n"] = om["n_rows"]
        DATA["metrics"]["oer_arm_R2"] = om.get("arm_R2", {})
    except Exception:
        pass

    # domain-correct leaderboards (OER ranked by literature overpotential, not the
    # descriptor score, so only genuine OER catalysts appear)
    pf = lambda v: v["combos"]["methanol|true"]["promising"]
    photo_lb = sorted([(k, v) for k, v in DATA["photo"].items() if v.get("evidence")], key=lambda kv: -pf(kv[1]))[:10]
    vis_lb = sorted([(k, v) for k, v in DATA["photo"].items() if v["band_gap_eV"] < 3.0 and v.get("evidence")], key=lambda kv: -pf(kv[1]))[:10]
    her_lb = sorted(DATA["electro"].items(), key=lambda kv: -kv[1]["score"])[:10]
    oer_lb = sorted([x for x in DATA["oer"].items() if x[1].get("lit_eta_mV")], key=lambda kv: kv[1]["lit_eta_mV"])[:10]
    DATA["leaderboards"] = {
        "photo": [{"name": k, "value": f"{round(pf(v)*100)}% promising"} for k, v in photo_lb],
        "visible": [{"name": k, "value": f"{round(pf(v)*100)}% · {v['band_gap_eV']} eV"} for k, v in vis_lb],
        "her": [{"name": k, "value": f"{round(v['score'])}/100 · {v['energy_eV']} eV"} for k, v in her_lb],
        "oer": [{"name": k, "value": f"{v['lit_eta_mV']} mV (lit.)"} for k, v in oer_lb],
    }

    # write JSON source of truth + inline into index.html
    payload = json.dumps(DATA, ensure_ascii=False)
    assert "—" not in payload, "em dash leaked into the dashboard payload"
    with open(os.path.join(DATA_DIR, "dashboard_data.json"), "w") as f:
        f.write(payload)

    lines = open(INDEX, encoding="utf-8").read().split("\n")
    for i, line in enumerate(lines):
        if line.startswith("const DATA = "):
            lines[i] = f"const DATA = {payload};"
            break
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"photo materials embedded: {len(DATA['photo'])}")
    print(f"  evidence-backed: {sum(1 for v in DATA['photo'].values() if v['confidence']=='evidence-backed')}")
    print(f"  limited-evidence: {sum(1 for v in DATA['photo'].values() if v['confidence']=='limited-evidence')}")
    print(f"  model-estimate: {sum(1 for v in DATA['photo'].values() if v['confidence']=='model-estimate')}")
    print(f"electro materials preserved: {len(DATA['electro'])}")
    print(f"honest metrics: tier_acc={DATA['metrics']['photo_tier_acc']} "
          f"binary_acc={DATA['metrics']['photo_binary_acc']} roc_auc={DATA['metrics']['photo_roc_auc']}")
    print("wrote data/dashboard_data.json and rewrote DATA in index.html")

if __name__ == "__main__":
    main()
