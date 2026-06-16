#!/usr/bin/env python3
"""
================================================================================
 build_photocatalyst_library.py  --  the RELIABLE 100+ photocatalyst whitelist
================================================================================
The text-mined evidence table is rich but noisy (it contains lamp gases like
xenon, scavengers like methanol, dyes like RhB, bare metals, and band-structure
abbreviations). Filtering that by blocklist is never fully reliable.

Instead we CURATE a whitelist of real semiconductor photocatalysts, each with a
literature experimental band gap and a material class. A material is only ever
offered in the dashboard if it is on this whitelist (so it is provably a real
photocatalyst with a real band gap) AND has published evidence in the corpus.

Band gap precedence per material:  curated chem_knowledge  >  measured expt_gap
(Zhuo/Brgoch, matched by reduced formula)  >  the literature value below.
Every literature value is cross-checked against expt_gap; large disagreements
are reported so they can be reconciled.

Output: data/photocatalysts_curated.csv  (material, band_gap_eV, gap_source,
        class, n_papers, median_rate, p25, p75)
================================================================================
"""
import os, re, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from pymatgen.core import Composition
import chem_knowledge as ck
from matminer.datasets import load_dataset
from paths import MODELS_DIR, DATA_DIR

# --------------------------------------------------------------------------- #
# Curated whitelist: material -> (literature band gap eV, class)
# Values are well-established semiconductor / photocatalysis literature gaps.
# --------------------------------------------------------------------------- #
WHITELIST = {
    # ---- binary oxides ----
    "TiO2": (3.20, "oxide"), "TiO2 (rutile)": (3.00, "oxide"), "ZnO": (3.30, "oxide"),
    "WO3": (2.70, "oxide"), "Fe2O3": (2.10, "oxide"), "Cu2O": (2.00, "oxide"),
    "CuO": (1.70, "oxide"), "SnO2": (3.60, "oxide"), "In2O3": (2.90, "oxide"),
    "NiO": (3.50, "oxide"), "Co3O4": (2.07, "oxide"), "Bi2O3": (2.80, "oxide"),
    "CeO2": (3.20, "oxide"), "Ta2O5": (3.90, "oxide"), "Nb2O5": (3.40, "oxide"),
    "V2O5": (2.30, "oxide"), "MoO3": (2.90, "oxide"), "Ga2O3": (4.80, "oxide"),
    "ZrO2": (5.00, "oxide"), "Ag2O": (1.30, "oxide"), "MnO2": (0.27, "oxide"),
    "CdO": (2.30, "oxide"), "SnO": (0.70, "oxide"), "Sn3O4": (2.70, "oxide"),
    "PbO": (2.80, "oxide"), "Bi2O2CO3": (3.30, "oxide"),
    # ---- ternary / complex oxides ----
    "BiVO4": (2.40, "oxide"), "Bi2WO6": (2.70, "oxide"), "Bi2MoO6": (2.66, "oxide"),
    "BiPO4": (3.85, "oxide"), "InVO4": (1.90, "oxide"), "Ag3PO4": (2.45, "oxide"),
    "ZnFe2O4": (1.90, "oxide"), "NiFe2O4": (1.70, "oxide"), "CuFe2O4": (1.42, "oxide"),
    "ZnGa2O4": (4.40, "oxide"), "AgVO3": (2.10, "oxide"), "Ag2CrO4": (1.80, "oxide"),
    "CuWO4": (2.30, "oxide"), "ZnWO4": (3.90, "oxide"), "FeWO4": (2.00, "oxide"),
    "MnWO4": (2.80, "oxide"), "Bi4Ti3O12": (3.00, "oxide"), "FeVO4": (2.00, "oxide"),
    # ---- perovskite oxides ----
    "SrTiO3": (3.20, "perovskite"), "BaTiO3": (3.20, "perovskite"),
    "NaTaO3": (4.00, "perovskite"), "KTaO3": (3.60, "perovskite"),
    "NaNbO3": (3.40, "perovskite"), "KNbO3": (3.10, "perovskite"),
    "LaFeO3": (2.10, "perovskite"), "CaTiO3": (3.50, "perovskite"),
    "PbTiO3": (3.40, "perovskite"), "BiFeO3": (2.20, "perovskite"),
    "AgNbO3": (2.80, "perovskite"), "AgTaO3": (3.40, "perovskite"),
    "LaCoO3": (2.00, "perovskite"), "CaNb2O6": (3.90, "perovskite"),
    # ---- halide perovskites ----
    "MAPbI3": (1.55, "halide_perovskite"), "CsPbBr3": (2.30, "halide_perovskite"),
    "Cs2AgBiBr6": (2.20, "halide_perovskite"),
    # ---- layered perovskite / niobate / titanate ----
    "La2Ti2O7": (3.80, "layered"), "K2La2Ti3O10": (3.05, "layered"),
    "K4Nb6O17": (3.30, "layered"), "HCa2Nb3O10": (3.40, "layered"),
    "Sr2Nb2O7": (3.90, "layered"), "KCa2Nb3O10": (3.50, "layered"),
    # ---- pyrochlores ----
    "Bi2Ti2O7": (2.90, "pyrochlore"), "Y2Ti2O7": (3.50, "pyrochlore"),
    "La2Zr2O7": (5.00, "pyrochlore"), "Bi2Sn2O7": (2.70, "pyrochlore"),
    "Gd2Ti2O7": (3.40, "pyrochlore"), "Sm2Ti2O7": (3.50, "pyrochlore"),
    "La2Sn2O7": (4.40, "pyrochlore"), "Y2Sn2O7": (4.20, "pyrochlore"),
    # ---- sulfides ----
    "CdS": (2.40, "sulfide"), "ZnS": (3.60, "sulfide"), "MoS2": (1.80, "sulfide"),
    "WS2": (1.35, "sulfide"), "SnS2": (2.20, "sulfide"), "SnS": (1.30, "sulfide"),
    "In2S3": (2.00, "sulfide"), "ZnIn2S4": (2.30, "sulfide"), "Bi2S3": (1.30, "sulfide"),
    "Sb2S3": (1.70, "sulfide"), "Ag2S": (1.00, "sulfide"), "CuS": (1.50, "sulfide"),
    "Cu2S": (1.20, "sulfide"), "NiS": (0.50, "sulfide"), "CdLa2S4": (2.50, "sulfide"),
    "CuInS2": (1.50, "sulfide"), "AgInS2": (1.80, "sulfide"), "MnS": (3.00, "sulfide"),
    "FeS2": (0.95, "sulfide"), "Zn0.5Cd0.5S": (2.40, "sulfide"), "MnCdS": (2.30, "sulfide"),
    "CoS": (0.50, "sulfide"), "SnS2/SnS": (1.80, "sulfide"), "ZnS/CdS": (2.60, "sulfide"),
    # ---- selenides ----
    "CdSe": (1.74, "selenide"), "ZnSe": (2.70, "selenide"), "MoSe2": (1.50, "selenide"),
    "WSe2": (1.60, "selenide"), "In2Se3": (1.30, "selenide"), "Sb2Se3": (1.20, "selenide"),
    "CuInSe2": (1.04, "selenide"), "Bi2Se3": (0.30, "selenide"), "CdSe/CdS": (2.00, "selenide"),
    # ---- tellurides ----
    "CdTe": (1.50, "telluride"), "ZnTe": (2.26, "telluride"), "Bi2Te3": (0.15, "telluride"),
    # ---- nitrides / carbon-based ----
    "g-C3N4": (2.70, "carbon_nitride"), "Ta3N5": (2.10, "nitride"),
    "GaN": (3.40, "nitride"), "Ge3N4": (3.80, "nitride"), "C3N5": (2.00, "carbon_nitride"),
    "SiC": (2.40, "other"), "carbon dots": (2.80, "carbon"),
    "graphene oxide": (2.20, "carbon"), "boron nitride": (5.90, "other"),
    # ---- MXene / framework / misc semiconductors ----
    "Ti3C2": (0.00, "mxene"), "black phosphorus": (1.50, "other"),
    "CTF": (2.70, "framework"), "COF": (2.50, "framework"), "MIL-125": (3.60, "framework"),
    "UiO-66": (3.90, "framework"), "red phosphorus": (1.80, "other"),
}

# Reconcile known-bad values in the public measured dataset (highest precedence).
# expt_gap erroneously lists MnS at 0.0 eV; MnS is a textbook wide-gap (~3.0 eV).
RECONCILE = {"MnS": 3.00}

def reduced(s):
    try: return Composition(re.sub(r"[^A-Za-z0-9().]","",str(s))).reduced_formula
    except Exception: return None

def main():
    # measured experimental gaps, keyed by reduced formula
    eg = load_dataset("expt_gap"); eg.columns = ["formula","gap"]
    measured = {}
    for _, r in eg.iterrows():
        k = reduced(r["formula"])
        if k is not None:
            measured.setdefault(k, float(r["gap"]))

    # evidence table -> per canonical material published range
    ev = pd.read_csv(os.path.join(MODELS_DIR, "photo_evidence_by_material.csv"))
    EXTRA = {"ZIS":"ZnIn2S4","ZCS":"Zn0.5Cd0.5S","CZS":"Zn0.5Cd0.5S",
             "Cd0.5Zn0.5S":"Zn0.5Cd0.5S","STO":"SrTiO3","BCN":"g-C3N4","PCN":"g-C3N4",
             "GCN":"g-C3N4","CN":"g-C3N4","ZnxCd1-xS":"Zn0.5Cd0.5S"}
    def canon(n):
        c = ck.canonicalize_name(n) or n
        return EXTRA.get(c, c)
    ev["canon"] = ev["material"].apply(canon)
    evg = ev.groupby("canon").agg(n=("n","sum"),
                                  median_rate=("median_rate","median"),
                                  p25=("p25","median"), p75=("p75","median")).reset_index()
    evmap = evg.set_index("canon").to_dict("index")

    rows, flags = [], []
    for mat, (lit_gap, cls) in WHITELIST.items():
        # gap precedence: reconcile > curated > measured(expt_gap) > literature
        if mat in RECONCILE:
            g, src = RECONCILE[mat], "reconciled"
        elif ck.experimental_gap(mat) is not None:
            g, src = ck.experimental_gap(mat), "curated"
        else:
            k = reduced(mat)
            if k in measured:
                g, src = measured[k], "measured(expt_gap)"
            else:
                g, src = lit_gap, "literature"
        # cross-check literature vs measured
        k = reduced(mat)
        if k in measured and abs(lit_gap - measured[k]) > 0.6:
            flags.append((mat, lit_gap, round(measured[k],2)))
        info = evmap.get(mat, {})
        rows.append({"material": mat, "band_gap_eV": round(float(g),2),
                     "gap_source": src, "class": cls,
                     "n_papers": int(info.get("n", 0)),
                     "median_rate": round(float(info["median_rate"]),1) if info.get("n") else None,
                     "p25": round(float(info["p25"]),1) if info.get("n") else None,
                     "p75": round(float(info["p75"]),1) if info.get("n") else None})

    df = pd.DataFrame(rows).sort_values(["n_papers","material"], ascending=[False, True])
    out = os.path.join(DATA_DIR, "photocatalysts_curated.csv")
    df.to_csv(out, index=False)

    has_ev = df[df.n_papers >= 3]
    print(f"curated whitelist photocatalysts: {len(df)}")
    print(f"  with published evidence (n>=3): {len(has_ev)}")
    print(f"  with published evidence (n>=1): {int((df.n_papers>=1).sum())}")
    print("  gap source:", df.gap_source.value_counts().to_dict())
    print("  classes:", df['class'].value_counts().to_dict())
    if flags:
        print("\n  CROSS-CHECK flags (literature vs measured differ > 0.6 eV, reconcile):")
        for m, lit, meas in flags:
            print(f"    {m}: literature {lit} vs measured {meas}")
    else:
        print("  cross-check: no literature/measured disagreements > 0.6 eV")
    print(f"\nwrote {out}")

if __name__ == "__main__":
    main()
