#!/usr/bin/env python3
"""
enrich_materials.py  --  per-material science + practical overlays for the dashboard.

Computes, for each curated photocatalyst, honest (flagged) extras:
  - band edges (CB/VB vs NHE) via the Mulliken electronegativity method
  - "can split water?" thermodynamic flag
  - solar absorption fraction + visible-light flag (from the band gap)
  - cost tier, toxicity flag, earth-abundance (element heuristics)
  - stability regime (curated by material class)
  - top source-paper citations (from the enriched modelling table)
Also builds leaderboards. Output: data/enrich.json
"""
import os, re, json, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from pymatgen.core import Composition
from paths import MODELS_DIR, DATA_DIR

# Mulliken absolute electronegativity (eV) for common elements
CHI = {
 "H":7.18,"Li":3.01,"Be":4.9,"B":4.29,"C":6.27,"N":7.30,"O":7.54,"F":10.41,"Na":2.85,"Mg":3.75,
 "Al":3.23,"Si":4.77,"P":5.62,"S":6.22,"Cl":8.30,"K":2.42,"Ca":2.2,"Sc":3.34,"Ti":3.45,"V":3.6,
 "Cr":3.72,"Mn":3.72,"Fe":4.06,"Co":4.3,"Ni":4.4,"Cu":4.48,"Zn":4.45,"Ga":3.2,"Ge":4.6,"As":5.3,
 "Se":5.89,"Br":7.59,"Rb":2.34,"Sr":2.0,"Y":3.19,"Zr":3.64,"Nb":4.0,"Mo":3.9,"Ru":4.5,"Rh":4.3,
 "Pd":4.45,"Ag":4.44,"Cd":4.33,"In":3.1,"Sn":4.30,"Sb":4.85,"Te":5.49,"I":6.76,"Cs":2.18,"Ba":2.4,
 "La":3.06,"Ce":3.06,"Ta":4.11,"W":4.4,"Re":4.0,"Ir":5.4,"Pt":5.6,"Au":5.77,"Hg":4.91,"Tl":3.2,
 "Pb":3.9,"Bi":4.69,"Gd":3.1,"Sm":3.1,
}
TOXIC = {"Cd","Pb","As","Hg","Tl","Be","Cr"}
PRECIOUS = {"Pt","Au","Ag","Pd","Ir","Ru","Rh","Re","Os"}
COSTLY = {"In","Ga","Te","Ta","Nb","La","Ce","Y","Gd","Sm","Cs","Rb"}
EE = 4.5  # free-electron energy vs vacuum (eV)

def elems(formula):
    try:
        return Composition(re.sub(r"[^A-Za-z0-9().]", "", str(formula))).get_el_amt_dict()
    except Exception:
        return {}

# Literature CB / VB band edges (V vs NHE, pH 0) for well-studied photocatalysts.
# Sources: standard photocatalysis / photoelectrochemistry literature.
BAND_EDGES_LIT = {
    "TiO2": (-0.29, 2.91), "TiO2 (rutile)": (-0.10, 2.90), "ZnO": (-0.31, 2.99),
    "CdS": (-0.52, 1.88), "ZnS": (-1.04, 2.56), "WO3": (0.37, 3.07), "Fe2O3": (0.28, 2.38),
    "g-C3N4": (-1.13, 1.57), "BiVO4": (0.02, 2.42), "Cu2O": (-1.00, 1.00), "CuO": (0.46, 2.16),
    "SnO2": (0.00, 3.60), "In2O3": (-0.62, 2.28), "SrTiO3": (-0.80, 2.40), "BaTiO3": (-0.80, 2.40),
    "Bi2WO6": (0.30, 3.00), "Bi2MoO6": (0.32, 2.98), "CdSe": (-0.60, 1.14), "MoS2": (-0.13, 1.67),
    "ZnIn2S4": (-0.86, 1.44), "Ag3PO4": (0.45, 2.90), "Ta3N5": (-0.75, 1.35), "CeO2": (-0.40, 2.80),
    "NaTaO3": (-1.06, 2.94), "KTaO3": (-0.90, 2.70), "Nb2O5": (-0.20, 3.20), "Ta2O5": (-0.60, 3.30),
    "ZrO2": (-1.00, 4.00), "Ga2O3": (-1.40, 3.40), "In2S3": (-0.90, 1.10), "Bi2S3": (0.10, 1.40),
    "SnS2": (-0.50, 1.70), "NiO": (-0.50, 3.00), "Co3O4": (0.50, 2.57), "V2O5": (0.50, 2.80),
    "Bi2O3": (0.32, 3.12), "WS2": (-0.10, 1.25), "MoSe2": (-0.20, 1.30), "Zn0.5Cd0.5S": (-0.70, 1.70),
    "Fe2O3 (hematite)": (0.28, 2.38), "BiOCl": (-0.10, 3.30), "Ag2S": (-0.30, 0.70),
}

def band_edges(formula, eg, name=None):
    if name in BAND_EDGES_LIT:
        cb, vb = BAND_EDGES_LIT[name]
        return round(cb, 2), round(vb, 2), "literature"
    d = elems(formula)
    if not d or any(e not in CHI for e in d):
        return None, None, "none"
    tot = sum(d.values())
    chi = 1.0
    for e, n in d.items():
        chi *= CHI[e] ** (n / tot)
    cb = chi - EE - 0.5 * eg     # Mulliken estimate, vs NHE pH 0
    vb = cb + eg
    return round(cb, 2), round(vb, 2), "estimated"

# AM1.5G absorbable photon fraction vs band gap (interpolated)
_SOLAR = [(1.0,0.77),(1.5,0.55),(2.0,0.36),(2.4,0.24),(2.7,0.17),(3.0,0.12),(3.2,0.09),(3.6,0.05),(4.0,0.03),(5.0,0.01)]
def solar_abs(eg):
    if eg <= _SOLAR[0][0]: return _SOLAR[0][1]
    if eg >= _SOLAR[-1][0]: return _SOLAR[-1][1]
    for i in range(len(_SOLAR)-1):
        x0,y0 = _SOLAR[i]; x1,y1 = _SOLAR[i+1]
        if x0 <= eg <= x1:
            return round(y0 + (y1-y0)*(eg-x0)/(x1-x0), 2)
    return 0.1

def practical(formula):
    d = elems(formula)
    es = set(d.keys())
    toxic = bool(es & TOXIC)
    if es & PRECIOUS: cost = "precious"
    elif es & COSTLY: cost = "moderate"
    else: cost = "low"
    abundant = not (es & PRECIOUS) and not (es & COSTLY)
    return {"cost": cost, "toxic": toxic, "abundant": abundant}

STAB = {
 "oxide": "Robust in both acid and alkaline.",
 "perovskite": "Generally robust oxide; stable across pH.",
 "pyrochlore": "Robust oxide framework.",
 "layered": "Stable layered oxide.",
 "sulfide": "Photocorrodes without a sacrificial agent or protective shell.",
 "selenide": "Prone to photocorrosion; use a sacrificial agent.",
 "telluride": "Easily oxidised; needs protection.",
 "nitride": "Moderately stable; can oxidise under strong OER.",
 "carbon_nitride": "Chemically stable, metal-free.",
 "carbon": "Stable support; activity depends on functionalisation.",
 "halide_perovskite": "Degrades in water; needs encapsulation.",
 "framework": "Stability depends on the framework and linker.",
 "mxene": "Oxidises in air and water over time.",
}

# OER applicability domain: a genuine OER catalyst needs a redox-active transition
# metal in an oxide-type framework. Main-group oxides (ZnO, Ag3PO4, CdO) are NOT.
OER_REDOX = {"Ni", "Co", "Fe", "Mn", "Ir", "Ru", "Rh", "Cu", "V", "Cr", "Mo", "W"}
OER_CLASSES = {"oxide", "perovskite", "pyrochlore", "layered"}
def oer_in_domain(formula, cls):
    es = set(elems(formula).keys())
    return bool(cls in OER_CLASSES and (es & OER_REDOX))

def doi_link(s):
    s = str(s)
    if s.startswith("10."):
        return s
    if s.startswith("j.") or s.startswith("S"):    # Elsevier PII-like
        return "10.1016/" + s
    return s

def main():
    lib = pd.read_csv(os.path.join(DATA_DIR, "photocatalysts_curated.csv"))
    # citations from the enriched modelling table
    enr = pd.read_csv(os.path.join(MODELS_DIR, "photo_enriched_table.csv"))
    cites = {}
    for mat, g in enr.groupby("material"):
        ps = [p for p in g["source_paper"].dropna().unique() if str(p) != "nan"][:4]
        if ps:
            cites[str(mat)] = [doi_link(p) for p in ps]

    out = {}
    for _, r in lib.iterrows():
        m = str(r["material"]); eg = float(r["band_gap_eV"]); cls = r["class"]
        gsrc = str(r.get("gap_source", "literature"))
        cb, vb, esrc = band_edges(m, eg, m)
        splits = None if esrc == "none" else bool(cb < 0 and vb > 1.23)
        out[m] = {
            "cb": cb, "vb": vb, "edge_source": esrc,
            "splits_water": splits,
            "solar_abs": solar_abs(eg), "visible": eg < 3.0,
            "gap_source": gsrc,
            **practical(m),
            "stability": STAB.get(cls, "Stability varies."),
            "oer_domain": oer_in_domain(m, cls),
            "papers": cites.get(m, []),
        }

    json.dump({"materials": out}, open(os.path.join(DATA_DIR, "enrich.json"), "w"))
    nbe = sum(1 for v in out.values() if v["cb"] is not None)
    ndom = sum(1 for v in out.values() if v["oer_domain"])
    print(f"enriched {len(out)} materials | band edges for {nbe} | OER-in-domain {ndom} | citations {len(cites)}")
    print("sample TiO2:", out.get("TiO2"))

if __name__ == "__main__":
    main()
