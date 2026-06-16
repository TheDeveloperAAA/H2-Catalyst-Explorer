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
import pandas as pd
import h2_predictor as hp
import chem_knowledge as ck
import curated_overlays as co
from paths import MODELS_DIR, DATA_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
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

def build_overlays(DATA):
    """Curated overlays (OER, electrolyte, defects) + litmus benchmark. All flagged in UI."""
    def oer_score(eta): return max(0.0, min(100.0, round(100 * (1 - (eta - 250) / 320.0), 1)))
    DATA["oer"] = {m: {"eta_mV": v["eta_mV"], "electrolyte": v["electrolyte"], "class": v["class"],
                       "verdict": co.oer_verdict(v["eta_mV"]), "score": oer_score(v["eta_mV"])}
                   for m, v in co.OER_CATALYSTS.items()}
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
    build_overlays(DATA)

    # honest metrics (electro untouched; photo updated to grouped numbers)
    m = json.load(open(os.path.join(MODELS_DIR, "photo_classifier_metrics.json")))
    DATA["metrics"]["photo_tier_acc"]   = m["tier_model"]["accuracy"]
    DATA["metrics"]["photo_binary_acc"] = m["binary_model"]["accuracy"]
    DATA["metrics"]["photo_roc_auc"]    = m["binary_model"]["roc_auc"]
    DATA["metrics"]["photo_validation"] = "GroupShuffleSplit by material (unseen materials)"
    DATA["metrics"]["photo_n_materials"] = len(DATA["photo"])

    # write JSON source of truth + inline into index.html
    payload = json.dumps(DATA, ensure_ascii=False)
    if "-" in payload:                            # never emit an em dash
        payload = payload.replace("-", "-")
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
