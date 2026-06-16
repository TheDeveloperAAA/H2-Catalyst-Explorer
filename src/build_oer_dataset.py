#!/usr/bin/env python3
"""
build_oer_dataset.py  --  pull OER intermediates (O*, OH*, OOH*) from Catalysis-Hub.

Lightweight GraphQL pull (no OC22 download). For each adsorbate we paginate the
public endpoint, parse the exact '*'-bound product, and keep clean rows with a
physical reaction energy. Output: data/oer_clean.csv
(surface_composition, facet, adsorbate, reaction_energy_eV).
"""
import os, re, json, time, warnings
warnings.filterwarnings("ignore")
import requests, pandas as pd, numpy as np
from paths import DATA_DIR

EP = "https://api.catalysis-hub.org/graphql"
PAGE = 500
# adsorbate filter -> max pages to pull (cap O* which has ~55k rows)
TARGETS = {"~OOHstar": 3, "~OHstar": 16, "~Ostar": 24}

def adsorbate(products):
    try:
        p = json.loads(products) if isinstance(products, str) else (products or {})
    except Exception:
        return None
    stars = [k for k in p.keys() if "star" in k.lower()]
    if len(stars) != 1:
        return None
    name = stars[0].lower().replace("star", "").upper()
    return (name + "*") if name else None

def fetch(filt, maxpages):
    rows, after, pages = [], "", 0
    while pages < maxpages:
        q = ('{reactions(products:"%s", first:%d, after:"%s"){pageInfo{hasNextPage endCursor}'
             'edges{node{reactionEnergy surfaceComposition facet products}}}}' % (filt, PAGE, after))
        for attempt in range(4):
            try:
                d = requests.post(EP, json={"query": q}, timeout=120).json()["data"]["reactions"]; break
            except Exception:
                if attempt == 3: raise
                time.sleep(2*(attempt+1))
        for e in d["edges"]:
            rows.append(e["node"])
        pages += 1
        if not d["pageInfo"]["hasNextPage"]: break
        after = d["pageInfo"]["endCursor"]
    return rows

all_rows = []
for filt, mp in TARGETS.items():
    r = fetch(filt, mp)
    print(f"  {filt}: pulled {len(r):,} raw")
    all_rows += r

df = pd.DataFrame(all_rows)
df["adsorbate"] = df["products"].apply(adsorbate)
df["reaction_energy_eV"] = pd.to_numeric(df["reactionEnergy"], errors="coerce")
df = df[df.adsorbate.isin(["O*", "OH*", "OOH*"])]
df = df[df.reaction_energy_eV.notna() & df.reaction_energy_eV.between(-6, 8)]
clean = (df[["surfaceComposition", "facet", "adsorbate", "reaction_energy_eV"]]
         .rename(columns={"surfaceComposition": "surface_composition"})
         .dropna(subset=["surface_composition"]).drop_duplicates().reset_index(drop=True))
out = os.path.join(DATA_DIR, "oer_clean.csv")
clean.to_csv(out, index=False)
print(f"\nOER dataset: {len(clean):,} rows | unique surfaces: {clean.surface_composition.nunique():,}")
print("by adsorbate:", clean.adsorbate.value_counts().to_dict())
print("wrote", out)
