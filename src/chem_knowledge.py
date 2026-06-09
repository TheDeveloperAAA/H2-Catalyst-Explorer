#!/usr/bin/env python3
"""
================================================================================
 chem_knowledge.py  --  Curated chemistry knowledge base
================================================================================
The trust foundation of the whole project. Three hand-curated resources that
prevent the model from embarrassing itself on materials Prof. Dutta knows cold:

  1. EXPERIMENTAL_BANDGAP : literature experimental band gaps (eV) for the
     showcase materials. DFT (Materials Project) underestimates these by up to
     4-5x (ZnO: DFT 0.72 eV vs experiment 3.3 eV), so we anchor the materials
     he works with to their REAL measured values.

  2. NAME_ALIASES : maps the many ways one material is written in the
     literature to a single canonical name (CdS / "cadmium sulfide" /
     "CdS; cadmium sulfide" -> CdS). Text-mining fragmented these; we reunite
     them so the model sees one material, not four.

  3. SCAVENGER_STRENGTH : an ordinal "hole-scavenging strength" for common
     sacrificial agents, so the model has a physically meaningful feature
     rather than a bare category.

All values are from standard photocatalysis literature and textbooks.
================================================================================
"""

# --------------------------------------------------------------------------- #
# 1. Experimental band gaps (eV) -- the materials Prof. Dutta actually uses.
#    Sources: standard semiconductor / photocatalysis literature.
# --------------------------------------------------------------------------- #
EXPERIMENTAL_BANDGAP = {
    # --- Prof. Dutta's core oxides / nitrides ---
    "ZnO": 3.30,                 # wurtzite, classic wide-gap oxide
    "TiO2": 3.20,                # anatase (P25 is mixed ~3.0-3.2)
    "TiO2 (rutile)": 3.00,
    "g-C3N4": 2.70,              # graphitic carbon nitride
    "C3N4": 2.70,
    "WO3": 2.70,
    "Fe2O3": 2.10,               # hematite
    "Cu2O": 2.00,
    "CuO": 1.70,
    "SnO2": 3.60,
    "In2O3": 2.90,
    # --- Sulfides (his CdS / ZnS / SnS2 work) ---
    "CdS": 2.40,
    "ZnS": 3.60,
    "CdTe": 1.50,                # his quantum-dot work (bulk; QDs tune higher)
    "CdSe": 1.74,
    "SnS2": 2.20,
    "MoS2": 1.80,                # monolayer ~1.8; bulk ~1.2
    "ZnIn2S4": 2.30,
    "Bi2S3": 1.30,
    # --- Bismuth / tin composites (his recent papers) ---
    "Bi2WO6": 2.70,
    "Bi2MoO6": 2.70,
    "BiVO4": 2.40,
    "Bi2O3": 2.80,
    "ZnWO4": 3.90,
    "FeWO4": 2.00,
    "Sn3O4": 2.70,
    "SnS": 1.30,
    # --- Carbon-dot / quantum-dot context (tunable; nominal anchors) ---
    "carbon dots": 2.80,
    "carbon quantum dots": 2.80,
    "graphene": 0.00,            # semimetal; used as conductive support
    "reduced graphene oxide": 0.00,
    "rGO": 0.00,
    "graphene oxide": 2.20,      # GO is semiconducting, gap varies with O content
    # --- Common co-catalyst metals (no gap; flagged metallic) ---
    "Pt": 0.00, "Au": 0.00, "Ag": 0.00, "Pd": 0.00, "Ni": 0.00,
    "Cu": 0.00, "Ru": 0.00, "Rh": 0.00,
    # --- Other frequently-studied photocatalysts ---
    "SrTiO3": 3.20,
    "Ta3N5": 2.10,
    "GaN": 3.40,
    "BaTiO3": 3.20,
    "NaTaO3": 4.00,
    "KTaO3": 3.60,
}

# --------------------------------------------------------------------------- #
# 2. Name aliases -> canonical name. Lower-cased keys for matching.
#    Handles the set-notation fragments we saw in the raw data.
# --------------------------------------------------------------------------- #
NAME_ALIASES = {
    "cadmium sulfide": "CdS",
    "cds; cadmium sulfide": "CdS",
    "cadmium sulfide; cds": "CdS",
    "cds; cds": "CdS",
    "titania": "TiO2",
    "titanium dioxide": "TiO2",
    "p25": "TiO2",
    "degussa p25": "TiO2",
    "tio2; titania": "TiO2",
    "tio2 (p25)": "TiO2",
    "anatase": "TiO2",
    "rutile": "TiO2 (rutile)",
    "cn": "g-C3N4",
    "c3n4": "g-C3N4",
    "g-c3n4": "g-C3N4",
    "gcn": "g-C3N4",
    "graphitic carbon nitride": "g-C3N4",
    "carbon nitride": "g-C3N4",
    "zinc oxide": "ZnO",
    "zno; zinc oxide": "ZnO",
    "zinc sulfide": "ZnS",
    "molybdenum disulfide": "MoS2",
    "mos2; molybdenum disulfide": "MoS2",
    "hematite": "Fe2O3",
    "cuprous oxide": "Cu2O",
    "platinum": "Pt",
    "gold": "Au",
    "silver": "Ag",
    "rgo": "reduced graphene oxide",
    "r-go": "reduced graphene oxide",
    "go": "graphene oxide",
}

# --------------------------------------------------------------------------- #
# 3. Hole-scavenger / sacrificial-agent strength (ordinal, 0-3).
#    Higher = more effective electron donor -> typically higher H2 rate.
# --------------------------------------------------------------------------- #
SCAVENGER_STRENGTH = {
    "none/unspecified": 0,
    "Na2S/Na2SO3": 3,      # strongest, standard for sulfide photocatalysts
    "TEOA": 3,             # triethanolamine, very common & effective
    "TEA": 2,
    "methanol": 2,
    "ethanol": 2,
    "glycerol": 2,
    "lactic_acid": 2,
    "ascorbic_acid": 2,
    "EDTA": 2,
    "other": 1,
}

def canonicalize_name(raw):
    """Map a raw photocatalyst string to a canonical material name."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key = s.lower().strip()
    if key in NAME_ALIASES:
        return NAME_ALIASES[key]
    # take the first fragment of a "; "-joined set and retry
    if ";" in s:
        first = s.split(";")[0].strip()
        if first.lower() in NAME_ALIASES:
            return NAME_ALIASES[first.lower()]
        return first
    return s

def experimental_gap(canonical_name):
    """Return experimental band gap (eV) if we have a curated value."""
    if canonical_name is None:
        return None
    return EXPERIMENTAL_BANDGAP.get(canonical_name)

if __name__ == "__main__":
    # quick sanity print
    print(f"Curated experimental band gaps: {len(EXPERIMENTAL_BANDGAP)} materials")
    print(f"Name aliases: {len(NAME_ALIASES)} mappings")
    for t in ["cadmium sulfide", "P25", "CN", "CdS; cadmium sulfide", "ZnO"]:
        c = canonicalize_name(t)
        print(f"  '{t}' -> '{c}'  (exp gap: {experimental_gap(c)} eV)")
