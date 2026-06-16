# H2 Catalyst Explorer - Phase 3 (v3) Pipeline

Goal: robust, reliable, reproducible upgrades that push every metric the data
physically allows into the near-excellent zone, plus an impressive 3D dashboard.
Excludes the professor's own lab data (only he has it); everything below I can
source, clean, EDA, and train myself.

## Honest metric ceilings (stated up front)
Near-excellent is achievable where the target is a clean DFT quantity. It is NOT
achievable where the data is intrinsically noisy, and we will not fake it.
- **HER regression**: R2 = 0.90 (done, near-excellent).
- **OER regression**: target R2 0.85-0.92 (same DFT/adsorption pipeline as HER).
- **Synthesizability / stability**: deterministic from DFT databases (a filter, not a fitted metric).
- **Uncertainty**: calibrated to ~90% empirical interval coverage.
- **Photo H2 screening**: honest ceiling ~0.65 (text-mined noise); only the lab's
  own morphology-resolved data can lift it, which is out of scope here.
- **Organic degradation**: target ROC-AUC 0.70-0.80 on assembled literature data
  (heterogeneous, so honestly mid-range), reinforced by evidence ranges.

## Reliable data sources (all auto-fetchable by me)
| Track | Source | Access | Volume |
|---|---|---|---|
| OER | Catalysis-Hub GraphQL (O*/OH*/OOH* reactions) | free API | 55k O*, 5.7k OH*, 369 OOH* |
| Stability | Materials Project `mp-api` + OQMD REST | free key / open | all 127+ materials |
| Descriptors | matminer (`expt_gap`), JARVIS (meta-GGA gaps), AFLOW | free | thousands |
| Crystal structures (3D viewer) | Materials Project CIF via `mp-api` | free key | per material |
| Degradation | open CC-BY SI tables (Data-in-Brief PMC5726756; Sci Rep TiO2-150; Chemosphere MOF-TC; ZnO-RhB) | open | ~500-1500 rows |
| Band edges | derived (Mulliken: E_CB = X - 4.5 - 0.5*Eg) | computed | all materials |
| OC22 (optional) | Figshare 6432790 IS2RE subset | free, heavy | enrichment only |

## Per-track pipeline (same rigor everywhere)
Every track runs the identical reliability harness:
1. **Ingest** from the source above into `data/` (committed, reproducible).
2. **EDA report first** (before any model): distributions, missingness map, class
   balance, correlation/collinearity, outlier + unit-sanity checks, and a grouped
   leakage audit. Written readout saved to `docs/eda/`.
3. **Featurize** (Magpie + curated band gap + derived band edges + conditions).
4. **Tune to the bias-variance optimum** with grouped k-fold CV (group by material),
   early stopping, regularization sweep; pick params at the CV-error minimum.
5. **Validate honestly**: held-out grouped test, multiple seeds (report mean +/- std),
   calibrated probabilities (isotonic) + conformal prediction intervals.
6. **Save** booster + encoders + honest metrics; regenerate dashboard DATA.

### Track A - OER trained model
Pull O*/OH*/OOH* reactions from Catalysis-Hub; train per-adsorbate reaction-energy
regressors (composition + facet + site), then compute the OER overpotential from
the standard scaling descriptor dG(O*)-dG(OH*). Replaces the current curated OER
reference with a trained model. Target R2 0.85-0.92.

### Track B - Synthesizability / stability filter
Pull formation energy + energy-above-hull (Materials Project, OQMD) for every
material; flag any recommendation that is thermodynamically unstable or hard to
make. Pure data lookup, deterministic, high reliability.

### Track C - SHAP explainability
TreeExplainer on every trained model; per-prediction force/waterfall + global
importances. Closes the original charter's unmet SHAP deliverable. No new data.

### Track D - Uncertainty quantification
Conformal prediction + isotonic calibration on the grouped validation sets, so
every output carries a rigorous interval. No new data.

### Track E - Organic degradation
Fetch the open CC-BY SI tables, harmonize units (% degradation, rate constant k),
dedupe, EDA, then train a degradation tier/screen classifier (grouped split,
pollutant as a feature) or ship curated-evidence ranges if coverage is thin.

### Track F - Inverse design
Use the trained HER/OER/photo models + descriptor databases to rank the candidate
composition space and surface novel high-potential materials, each with its
confidence badge and stability flag.

## 3D dashboard (impressive, still self-contained)
Bundle Plotly.js + 3Dmol.js into a local `lib/` folder (no CDN) so the file stays
offline, the property the professor values. New 3D features:
1. **3D interactive Sabatier volcano** (HER + OER): rotatable activity landscape
   with every catalyst plotted on it.
2. **3D materials universe**: all 127+ photocatalysts in (band gap x band-edge x
   promising) space, color by class/tier, hover for details, rotate/zoom.
3. **3D crystal-structure viewer** (3Dmol.js): pick a material, see its real unit
   cell rotating (CIF from Materials Project).
4. **3D band-alignment / Z-scheme** diagram for heterostructures (ties to Defects tab).
5. **3D periodic-table contribution map**: which elements drive performance, as
   animated 3D bars (from SHAP).

## Validation + non-regression gate (unchanged discipline)
Frozen baseline tag, every existing material/tab byte-identical or a deliberate
upgrade, zero console errors, fully offline, promotion to live only after the gate
passes. Confidence labels (trained / evidence-backed / curated) on every output.

## Suggested execution order
1. Track A (OER trained) + Track B (stability) - both pure DFT data, near-excellent, no download.
2. Track C (SHAP) + Track D (uncertainty) - no data, deepen trust.
3. 3D dashboard features (bundle libs, add the 5 views).
4. Track E (degradation) - data-survey-gated.
5. Track F (inverse design) - the finale.
