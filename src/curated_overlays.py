#!/usr/bin/env python3
"""
================================================================================
 curated_overlays.py  --  honest curated knowledge for the data-limited sections
================================================================================
The professor asked for OER, alkaline/acidic electrolytes, a defects /
heterostructure section, and organic-degradation. As the data-sourcing pass
confirmed, NONE of these can be learned from the available datasets (composition
DFT is pH-blind; no ML-ready defect/heterostructure/degradation corpus exists).

So they are delivered as CURATED overlays: real literature values and
well-established directional rules, every one flagged "curated guidance, not a
model output" in the UI. This is the same trust pattern as the experimental
band-gap layer that makes the tool credible.
================================================================================
"""

# --------------------------------------------------------------------------- #
# OER electrocatalysts: literature overpotential @ 10 mA/cm2 (mV) + best
# electrolyte regime. Values are representative of well-cited reports; treat as
# screening guidance, not measured constants.
# --------------------------------------------------------------------------- #
OER_CATALYSTS = {
    # acidic-regime (noble oxides)
    "RuO2":   {"eta_mV": 280, "electrolyte": "acidic",  "class": "oxide"},
    "IrO2":   {"eta_mV": 320, "electrolyte": "acidic",  "class": "oxide"},
    "SrIrO3": {"eta_mV": 270, "electrolyte": "acidic",  "class": "perovskite"},
    # alkaline-regime (earth-abundant)
    "NiFe LDH":  {"eta_mV": 240, "electrolyte": "alkaline", "class": "layered hydroxide"},
    "NiFeOOH":   {"eta_mV": 250, "electrolyte": "alkaline", "class": "oxyhydroxide"},
    "CoOOH":     {"eta_mV": 300, "electrolyte": "alkaline", "class": "oxyhydroxide"},
    "NiOOH":     {"eta_mV": 310, "electrolyte": "alkaline", "class": "oxyhydroxide"},
    "Co3O4":     {"eta_mV": 320, "electrolyte": "alkaline", "class": "oxide"},
    "NiCo2O4":   {"eta_mV": 320, "electrolyte": "alkaline", "class": "oxide"},
    "CoFe2O4":   {"eta_mV": 370, "electrolyte": "alkaline", "class": "oxide"},
    "NiFe2O4":   {"eta_mV": 340, "electrolyte": "alkaline", "class": "oxide"},
    "Ni(OH)2":   {"eta_mV": 330, "electrolyte": "alkaline", "class": "hydroxide"},
    "FeOOH":     {"eta_mV": 350, "electrolyte": "alkaline", "class": "oxyhydroxide"},
    "MnO2":      {"eta_mV": 400, "electrolyte": "neutral",  "class": "oxide"},
    "LaNiO3":    {"eta_mV": 350, "electrolyte": "alkaline", "class": "perovskite"},
    "LaCoO3":    {"eta_mV": 400, "electrolyte": "alkaline", "class": "perovskite"},
    "BSCF":      {"eta_mV": 360, "electrolyte": "alkaline", "class": "perovskite"},
    "Ba2Co9O14": {"eta_mV": 420, "electrolyte": "alkaline", "class": "oxide"},
    "Fe2O3":     {"eta_mV": 480, "electrolyte": "alkaline", "class": "oxide"},
    "CuO":       {"eta_mV": 430, "electrolyte": "alkaline", "class": "oxide"},
    "Mn2O3":     {"eta_mV": 450, "electrolyte": "alkaline", "class": "oxide"},
    "Y2Ir2O7":   {"eta_mV": 300, "electrolyte": "acidic",   "class": "pyrochlore"},
    "Bi2Ir2O7":  {"eta_mV": 330, "electrolyte": "acidic",   "class": "pyrochlore"},
    "CoP":       {"eta_mV": 340, "electrolyte": "alkaline", "class": "phosphide"},
    "Ni2P":      {"eta_mV": 330, "electrolyte": "alkaline", "class": "phosphide"},
}

def oer_verdict(eta):
    if eta <= 280:  return "Excellent OER catalyst (low overpotential)"
    if eta <= 340:  return "Good OER catalyst"
    if eta <= 420:  return "Moderate OER activity"
    return "Poor - high overpotential"

# --------------------------------------------------------------------------- #
# Electrolyte guidance for HER metals (composition DFT cannot learn this; these
# are textbook regime preferences).
# --------------------------------------------------------------------------- #
HER_ELECTROLYTE = {
    "acidic":   {"Pt","Pd","Ir","Rh","Ru","Au","Ag","PtNi","PtCo","PtRu","MoS2"},
    "alkaline": {"Ni","NiFe","CuNi","Co","Fe","MoS2","Mo","W"},
}
def her_electrolyte_note(surface, electrolyte):
    s = HER_ELECTROLYTE.get(electrolyte, set())
    if surface in s:
        return f"Well-suited to {electrolyte} conditions"
    other = "alkaline" if electrolyte == "acidic" else "acidic"
    if surface in HER_ELECTROLYTE.get(other, set()):
        return f"Typically run in {other}; {electrolyte} less favourable"
    return f"Usable in {electrolyte}; check stability"

# --------------------------------------------------------------------------- #
# Defect / heterostructure modifiers: directional, semi-quantitative lifts on
# the promising-probability, from established photocatalysis literature. These
# are HEURISTIC, shown with a confidence flag, never as a model output.
# --------------------------------------------------------------------------- #
DEFECT_EFFECTS = {
    "oxygen_vacancy":      {"delta": 0.15, "note": "O-vacancies add mid-gap states and improve charge separation; commonly lift visible-light H2."},
    "metal_vacancy":       {"delta": 0.06, "note": "Cation (Schottky/point) vacancies tune band structure; usually a modest lift."},
    "nonmetal_doping":     {"delta": 0.12, "note": "N/S/C doping narrows the effective gap and extends visible-light absorption."},
    "metal_doping":        {"delta": 0.10, "note": "Transition-metal doping adds trap states and can boost charge separation."},
    "heterostructure":     {"delta": 0.20, "note": "A type-II / Z-scheme junction (e.g. ZnO/TiO2, g-C3N4/CdS) strongly improves charge separation."},
    "cocatalyst_loading":  {"delta": 0.12, "note": "An optimal noble-metal or earth-abundant co-catalyst forms a Schottky junction that extracts electrons."},
    "surface_modification":{"delta": 0.08, "note": "Surface passivation / facet engineering reduces recombination."},
}

# --------------------------------------------------------------------------- #
# Band-edge positions (CB/VB vs NHE at pH 0) computed from the curated band gap
# via the Mulliken electronegativity method: E_CB = X - 4.5 - 0.5*Eg.
# X (geometric-mean absolute electronegativity) is supplied per material where
# tabulated; otherwise the dashboard derives it on the fly.
# --------------------------------------------------------------------------- #
WATER_REDOX = {"H+/H2": 0.0, "O2/H2O": 1.23}   # vs NHE at pH 0
