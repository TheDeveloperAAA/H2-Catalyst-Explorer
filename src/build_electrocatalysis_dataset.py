#!/usr/bin/env python3
"""
================================================================================
 build_electrocatalysis_dataset.py
================================================================================
Pulls HER/OER adsorption-energy data from Catalysis-Hub for Model A
(electrocatalytic H2, target = adsorption / reaction energy in eV).

WHY GRAPHQL (not the cathub SQL API):
  The cathub Python client connects to a PostgreSQL host on AWS RDS that is
  not reachable from every environment. Catalysis-Hub exposes the *same*
  reaction-energy data through a public GraphQL endpoint
  (https://api.catalysis-hub.org/graphql), which IS reachable and needs no key.
  This script paginates that endpoint.

WHAT IT EXTRACTS  (per reaction):
  Equation, reactionEnergy (eV), chemicalComposition, surfaceComposition,
  facet, adsorption sites, reactants/products, DFT code + functional.

TARGET DEFINITION:
  We tag each reaction with the adsorbate (H* for HER-relevant, O*/OH*/OOH*
  for OER-relevant) parsed from the equation, so the downstream model can
  predict reaction energy per adsorbate family.

OUTPUT
  /mnt/user-data/outputs/electrocatalysis_clean.csv
  /mnt/user-data/outputs/electrocatalysis_quality_report.txt
"""

import os
import re
import json
import time
import requests
import pandas as pd
import numpy as np

ENDPOINT = "https://api.catalysis-hub.org/graphql"
OUT_CSV = "/mnt/user-data/outputs/electrocatalysis_clean.csv"
OUT_REPORT = "/mnt/user-data/outputs/electrocatalysis_quality_report.txt"

# Publications to pull. MamunHighT2019 is the large high-throughput bimetallic
# alloy study (the backbone of the IIT-Madras HER/OER reference set).
PUB_IDS = ["MamunHighT2019"]
PAGE = 500            # records per GraphQL page
MAX_RECORDS = 60000   # safety cap

report = []
def log(m):
    print(m)
    report.append(m)

log("=" * 70)
log("ELECTROCATALYSIS DATASET BUILD  (Model A: HER/OER reaction energies)")
log("Source: Catalysis-Hub GraphQL API  (no key required)")
log("=" * 70)

def fetch_pub(pub_id):
    """Paginate all reactions for one publication via GraphQL cursor."""
    rows, after, fetched = [], "", 0
    while True:
        q = """
        query($pid:String!,$n:Int!,$after:String!){
          reactions(pubId:$pid, first:$n, after:$after){
            pageInfo{ hasNextPage endCursor }
            edges{ node{
              Equation reactionEnergy activationEnergy
              chemicalComposition surfaceComposition facet sites
              reactants products dftCode dftFunctional
            }}
          }
        }"""
        variables = {"pid": pub_id, "n": PAGE, "after": after}
        for attempt in range(4):
            try:
                r = requests.post(ENDPOINT, json={"query": q, "variables": variables}, timeout=120)
                r.raise_for_status()
                data = r.json()["data"]["reactions"]
                break
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        for e in data["edges"]:
            rows.append(e["node"])
        fetched += len(data["edges"])
        log(f"    {pub_id}: fetched {fetched:,} ...")
        if not data["pageInfo"]["hasNextPage"] or fetched >= MAX_RECORDS:
            break
        after = data["pageInfo"]["endCursor"]
    return rows

# --------------------------------------------------------------------------- #
#  1. Fetch
# --------------------------------------------------------------------------- #
all_rows = []
for pid in PUB_IDS:
    log(f"\n[1] Pulling publication '{pid}' ...")
    all_rows.extend(fetch_pub(pid))

raw = pd.DataFrame(all_rows)
log(f"\n    TOTAL RAW REACTIONS: {len(raw):,}")

# --------------------------------------------------------------------------- #
#  2. Parse adsorbate from the equation and assign HER/OER relevance
# --------------------------------------------------------------------------- #
def adsorbate_from_products(products):
    """Identify the adsorbed species (the '*'-bound product)."""
    try:
        p = json.loads(products) if isinstance(products, str) else (products or {})
    except Exception:
        p = {}
    star_species = [k for k in p.keys() if "star" in k.lower()]
    # normalise e.g. 'OHstar' -> 'OH*', 'Hstar' -> 'H*'
    out = []
    for s in star_species:
        name = s.lower().replace("star", "").upper()
        out.append(name + "*" if name else "*")
    return ";".join(sorted(out)) if out else np.nan

raw["adsorbate"] = raw["products"].apply(adsorbate_from_products)

HER_ADS = {"H*"}
OER_ADS = {"O*", "OH*", "OOH*"}
def reaction_class(ads):
    if pd.isna(ads):
        return "other"
    parts = set(ads.split(";"))
    if parts & HER_ADS:
        return "HER"
    if parts & OER_ADS:
        return "OER"
    return "other"

raw["reaction_class"] = raw["adsorbate"].apply(reaction_class)

# --------------------------------------------------------------------------- #
#  3. Numeric target + clean fields
# --------------------------------------------------------------------------- #
raw["reaction_energy_eV"] = pd.to_numeric(raw["reactionEnergy"], errors="coerce")
raw["activation_energy_eV"] = pd.to_numeric(raw["activationEnergy"], errors="coerce")

def parse_site(sites):
    """Flatten the sites dict to a compact descriptor string."""
    try:
        s = json.loads(sites) if isinstance(sites, str) else (sites or {})
    except Exception:
        return np.nan
    if not s:
        return np.nan
    return ";".join(f"{k}:{v}" for k, v in s.items())

raw["site_descriptor"] = raw["sites"].apply(parse_site)

clean = pd.DataFrame({
    "equation":            raw["Equation"],
    "reaction_class":      raw["reaction_class"],
    "adsorbate":           raw["adsorbate"],
    "reaction_energy_eV":  raw["reaction_energy_eV"],   # <-- ML target
    "activation_energy_eV": raw["activation_energy_eV"],
    "chemical_composition": raw["chemicalComposition"],
    "surface_composition":  raw["surfaceComposition"],
    "facet":               raw["facet"],
    "site_descriptor":     raw["site_descriptor"],
    "dft_code":            raw["dftCode"],
    "dft_functional":      raw["dftFunctional"],
})

# Require a usable target
before = len(clean)
clean = clean[clean["reaction_energy_eV"].notna()].copy()
# physical sanity bound on adsorption/reaction energies
clean = clean[clean["reaction_energy_eV"].between(-10, 10)]
clean = clean.drop_duplicates().reset_index(drop=True)

# --------------------------------------------------------------------------- #
#  Report
# --------------------------------------------------------------------------- #
log("\n[2/3] Reaction-class breakdown:")
for k, c in clean["reaction_class"].value_counts().items():
    log(f"        {k:<8} {c:>7,}")
log("\n      Adsorbate breakdown (top 10):")
for k, c in clean["adsorbate"].value_counts().head(10).items():
    log(f"        {str(k):<10} {c:>7,}")

log("\n" + "=" * 70)
log("SUMMARY")
log("=" * 70)
log(f"  Raw reactions pulled .............. {before:,}")
log(f"  Clean reactions (valid energy) .... {len(clean):,}")
her = clean[clean.reaction_class == 'HER']
oer = clean[clean.reaction_class == 'OER']
log(f"  HER-relevant (H* adsorption) ...... {len(her):,}")
log(f"  OER-relevant (O*/OH*/OOH*) ........ {len(oer):,}")
log(f"  Unique surface compositions ....... {clean['surface_composition'].nunique():,}")
log(f"  Unique facets ..................... {clean['facet'].nunique():,}")
if len(her):
    log(f"  HER  energy mean +/- std (eV) ..... "
        f"{her.reaction_energy_eV.mean():.3f} +/- {her.reaction_energy_eV.std():.3f}")
if len(oer):
    log(f"  OER  energy mean +/- std (eV) ..... "
        f"{oer.reaction_energy_eV.mean():.3f} +/- {oer.reaction_energy_eV.std():.3f}")

os.makedirs("/mnt/user-data/outputs", exist_ok=True)
clean.to_csv(OUT_CSV, index=False)
with open(OUT_REPORT, "w") as f:
    f.write("\n".join(report))
log(f"\nWROTE: {OUT_CSV}")
log(f"WROTE: {OUT_REPORT}")
