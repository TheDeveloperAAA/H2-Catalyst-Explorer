#!/usr/bin/env python3
"""
================================================================================
 build_photocatalysis_dataset.py
================================================================================
Consolidates the Isazawa & Cole (2023) auto-generated photocatalysis
water-splitting database (Figshare DOI 10.6084/m9.figshare.21932211) into a
single ML-ready CSV for Model B (photocatalytic H2 evolution).

WHAT THIS DOES
  1. Walks all per-paper CSVs across the 4 publisher/query folders.
  2. Concatenates them, tagging each row with its source paper DOI + folder.
  3. Filters to hydrogen-evolution records (the prediction target).
  4. Normalises the messy activity units to a single canonical unit
     (umol h^-1 g^-1) where the conversion is unambiguous.
  5. Cleans set-notation chemical names  {'PCNT-3-5'} -> PCNT-3-5.
  6. Parses wavelength (handles  >=420 ,  ~350  etc).
  7. Encodes the hole-scavenger / sacrificial agent as an explicit feature
     (critical: photocatalytic H2 rates are meaningless without this control).
  8. De-duplicates and writes a clean CSV + a data-quality report.

OUTPUT
  /mnt/user-data/outputs/photocatalysis_clean.csv
  /mnt/user-data/outputs/photocatalysis_quality_report.txt
================================================================================
"""

import os
import re
import glob
import ast
import pandas as pd
import numpy as np

# --------------------------------------------------------------------------- #
#  Paths
# --------------------------------------------------------------------------- #
CSV_ROOT = "/home/claude/photocat/extracted/Photocatalyst Extracted Data/csv_version"
OUT_CSV = "/mnt/user-data/outputs/photocatalysis_clean.csv"
OUT_REPORT = "/mnt/user-data/outputs/photocatalysis_quality_report.txt"

report_lines = []
def log(msg):
    print(msg)
    report_lines.append(msg)

log("=" * 70)
log("PHOTOCATALYSIS DATASET BUILD  (Model B: H2 evolution)")
log("Source: Isazawa & Cole 2023, Figshare 10.6084/m9.figshare.21932211")
log("=" * 70)

# --------------------------------------------------------------------------- #
#  1. Load and concatenate every per-paper CSV
# --------------------------------------------------------------------------- #
all_csvs = glob.glob(os.path.join(CSV_ROOT, "*", "*.csv"))
log(f"\n[1] Found {len(all_csvs):,} per-paper CSV files across publisher/query folders.")

frames = []
n_empty = 0
for path in all_csvs:
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception:
        continue
    if df.shape[0] == 0:
        n_empty += 1
        continue
    folder = os.path.basename(os.path.dirname(path))      # e.g. elsevier_query_1
    paper_doi = os.path.splitext(os.path.basename(path))[0]
    df["source_folder"] = folder
    df["source_paper"] = paper_doi
    df["publisher"] = folder.split("_query")[0]
    df["search_query"] = "query_" + folder.split("query_")[-1]
    frames.append(df)

raw = pd.concat(frames, ignore_index=True)
log(f"    Empty CSVs (papers with no extractable records): {n_empty:,}")
log(f"    Papers contributing >=1 record: {len(frames):,}")
log(f"    TOTAL RAW RECORDS: {len(raw):,}")
log(f"    Record-type breakdown (top 12):")
for rt, c in raw["Record Type"].value_counts().head(12).items():
    log(f"        {rt:<28} {c:>6,}")

# --------------------------------------------------------------------------- #
#  2. Keep hydrogen-evolution records (our target). The text-miner emitted
#     several variants: HydrogenEvolution, HydrogenEvolution2/3, etc.
# --------------------------------------------------------------------------- #
he_mask = raw["Record Type"].astype(str).str.startswith("HydrogenEvolution")
he = raw[he_mask].copy()
log(f"\n[2] Hydrogen-evolution records retained: {len(he):,}")

# --------------------------------------------------------------------------- #
#  Helper: clean ChemDataExtractor set-notation names  {'A','B'} -> "A; B"
# --------------------------------------------------------------------------- #
def clean_name_set(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    if not s or s in ("{}", "set()"):
        return np.nan
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (set, list, tuple)):
            items = [str(x).strip() for x in parsed if str(x).strip()]
            return "; ".join(sorted(items)) if items else np.nan
    except Exception:
        pass
    # fallback: strip braces/quotes manually
    s = re.sub(r"[{}']", "", s).strip()
    return s if s else np.nan

for col in ["Photocatalyst Names", "Cocatalyst Names", "Additive Names"]:
    he[col] = he[col].apply(clean_name_set)

# --------------------------------------------------------------------------- #
#  3. Numeric activity value
# --------------------------------------------------------------------------- #
he["Activity Value"] = pd.to_numeric(he["Activity Value"], errors="coerce")

# --------------------------------------------------------------------------- #
#  4. Unit normalisation -> canonical  umol h^-1 g^-1
#     We only convert where the mapping is UNAMBIGUOUS. Rate units that are
#     not per-gram (e.g. umol/h alone) cannot be made per-gram without the
#     catalyst mass, so we keep them but flag them as a different basis.
# --------------------------------------------------------------------------- #
def normalise_units(u):
    if pd.isna(u):
        return np.nan
    s = str(u).lower().strip()
    s = (s.replace("−", "-").replace("·", "")
           .replace(" ", "").replace("μ", "u").replace("µ", "u"))
    return s

he["unit_norm"] = he["Activity Units"].apply(normalise_units)

# canonical target = umol h^-1 g^-1  (per-gram per-hour, the field standard)
PER_GRAM_PER_HOUR = {
    "umolh-1g-1", "umol/h/g", "umolg-1h-1", "umol/g/h",
    "umolh-1g-1", "umolhg", "umolh-1g-1",
}
def to_canonical(row):
    """Return (value_in_umol_h-1_g-1 or NaN, basis_label)."""
    v, u = row["Activity Value"], row["unit_norm"]
    if pd.isna(v) or pd.isna(u):
        return (np.nan, "unknown")
    # already per-gram per-hour
    if u in PER_GRAM_PER_HOUR or ("umol" in u and "h" in u and "g" in u):
        return (v, "umol_h-1_g-1")
    # mmol h-1 g-1 -> *1000
    if "mmol" in u and "h" in u and "g" in u:
        return (v * 1000.0, "umol_h-1_g-1")
    # per-gram per-hour cannot be derived; keep value, different basis
    if "umol" in u and "h" in u:        # umol/h (no mass)
        return (v, "umol_h-1 (no mass)")
    if "%" in u:                         # apparent quantum yield slipped in
        return (np.nan, "percent_QY")
    return (np.nan, "other:" + u[:18])

conv = he.apply(to_canonical, axis=1, result_type="expand")
he["activity_umol_h_g"] = conv[0]
he["activity_basis"] = conv[1]

log("\n[4] Activity-unit normalisation (basis breakdown):")
for b, c in he["activity_basis"].value_counts().head(12).items():
    log(f"        {b:<24} {c:>6,}")

# --------------------------------------------------------------------------- #
#  5. Wavelength parsing  ('>=420', '~350', '420-450' -> numeric)
# --------------------------------------------------------------------------- #
def parse_wavelength(v):
    if pd.isna(v):
        return np.nan
    s = str(v).replace("−", "-")
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums:
        return np.nan
    nums = [float(n) for n in nums]
    return float(np.mean(nums))      # midpoint for ranges, the value otherwise

he["wavelength_nm"] = he["Light Source Wavelength Value"].apply(parse_wavelength)
he["light_power_W"] = pd.to_numeric(he["Light Source Power Value"], errors="coerce")
he["irradiation_time_h"] = pd.to_numeric(he["Irradiation Time Value"], errors="coerce")

# --------------------------------------------------------------------------- #
#  6. Sacrificial-agent / hole-scavenger feature (CRITICAL CONTROL)
#     We classify the Additive into common scavenger families so the model
#     can condition on it instead of being confounded by it.
# --------------------------------------------------------------------------- #
SCAVENGER_MAP = {
    "teoa": "TEOA", "triethanolamine": "TEOA",
    "methanol": "methanol", "ch3oh": "methanol", "meoh": "methanol",
    "ethanol": "ethanol",
    "glycerol": "glycerol",
    "lactic": "lactic_acid",
    "na2s": "Na2S/Na2SO3", "na2so3": "Na2S/Na2SO3", "sulfide": "Na2S/Na2SO3",
    "teda": "TEA", "tea": "TEA", "triethylamine": "TEA",
    "edta": "EDTA",
    "ascorbic": "ascorbic_acid",
    "lactdate": "lactic_acid",
}
def classify_scavenger(additive):
    if pd.isna(additive):
        return "none/unspecified"
    a = str(additive).lower()
    for key, label in SCAVENGER_MAP.items():
        if key in a:
            return label
    return "other"

he["sacrificial_agent"] = he["Additive Names"].apply(classify_scavenger)
he["has_cocatalyst"] = he["Cocatalyst Names"].notna()

log("\n[6] Sacrificial-agent (hole scavenger) distribution:")
for s, c in he["sacrificial_agent"].value_counts().head(12).items():
    log(f"        {s:<20} {c:>6,}")

# --------------------------------------------------------------------------- #
#  7. Assemble the clean, ML-ready frame
# --------------------------------------------------------------------------- #
clean = pd.DataFrame({
    "photocatalyst":      he["Photocatalyst Names"],
    "cocatalyst":         he["Cocatalyst Names"],
    "has_cocatalyst":     he["has_cocatalyst"],
    "sacrificial_agent":  he["sacrificial_agent"],
    "additive_raw":       he["Additive Names"],
    "activity_value":     he["activity_umol_h_g"],          # canonical target
    "activity_basis":     he["activity_basis"],
    "activity_raw_value": he["Activity Value"],
    "activity_raw_units": he["Activity Units"],
    "light_source":       he["Light Source Name"],
    "wavelength_nm":      he["wavelength_nm"],
    "light_power_W":      he["light_power_W"],
    "irradiation_time_h": he["irradiation_time_h"],
    "publisher":          he["publisher"],
    "search_query":       he["search_query"],
    "source_paper":       he["source_paper"],
})

# Require at least a catalyst name and SOME activity number to be useful
clean = clean[clean["photocatalyst"].notna() & clean["activity_raw_value"].notna()].copy()

# --------------------------------------------------------------------------- #
#  8. De-duplication
# --------------------------------------------------------------------------- #
before = len(clean)
clean = clean.drop_duplicates(
    subset=["photocatalyst", "activity_raw_value", "activity_raw_units",
            "sacrificial_agent", "wavelength_nm", "source_paper"]
).reset_index(drop=True)
log(f"\n[8] De-duplication: {before:,} -> {len(clean):,} rows "
    f"({before - len(clean):,} exact duplicates removed).")

# --------------------------------------------------------------------------- #
#  Modelling subset: rows with a usable per-gram-per-hour target
# --------------------------------------------------------------------------- #
model_ready = clean[clean["activity_basis"] == "umol_h-1_g-1"].copy()
# light outlier guard: drop absurd/negative rates
model_ready = model_ready[(model_ready["activity_value"] > 0) &
                          (model_ready["activity_value"] < 1e7)]

log("\n" + "=" * 70)
log("SUMMARY")
log("=" * 70)
log(f"  Clean records (any activity basis) ... {len(clean):,}")
log(f"  Model-ready (umol h-1 g-1 target) .... {len(model_ready):,}")
log(f"  Unique photocatalysts ................ {clean['photocatalyst'].nunique():,}")
log(f"  Records WITH a defined scavenger ..... "
    f"{(clean['sacrificial_agent'] != 'none/unspecified').sum():,}")
if len(model_ready):
    q = model_ready["activity_value"].describe(percentiles=[.25, .5, .75, .95])
    log(f"  Target (umol h-1 g-1) median ......... {q['50%']:.1f}")
    log(f"  Target 95th percentile ............... {q['95%']:.1f}")

# --------------------------------------------------------------------------- #
#  Write outputs
# --------------------------------------------------------------------------- #
os.makedirs("/mnt/user-data/outputs", exist_ok=True)
clean.to_csv(OUT_CSV, index=False)
with open(OUT_REPORT, "w") as f:
    f.write("\n".join(report_lines))
log(f"\nWROTE: {OUT_CSV}")
log(f"WROTE: {OUT_REPORT}")
