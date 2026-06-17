#!/usr/bin/env python3
"""
rebuild.py  --  one-command regeneration of every model + the dashboard data.

Runs the full pipeline from on-disk data. The OER pull (build_oer_dataset) needs
internet; pass --offline to reuse the cached data/oer_clean.csv.

    python src/rebuild.py            # full
    python src/rebuild.py --offline  # skip network pulls, reuse cached CSVs

After it finishes:  cd app && npm run build   then copy app/dist to the repo root.
"""
import os, sys, subprocess, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV = {**os.environ, "PYTHONPATH": HERE}

def run(script, *args):
    print(f"\n{'=' * 60}\n  {script} {' '.join(args)}\n{'=' * 60}")
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], check=True, env=ENV)

def main():
    offline = "--offline" in sys.argv
    run("build_photocatalyst_library.py")
    run("train_photo_grouped.py", "--save")
    if not offline:
        run("build_oer_dataset.py")
    run("train_oer.py")
    run("compute_shap.py")
    run("enrich_materials.py")
    run("compute_uncertainty.py")
    run("build_dashboard_data.py")
    shutil.copy(os.path.join(ROOT, "data", "dashboard_data.json"),
                os.path.join(ROOT, "app", "src", "data.json"))
    print("\nPipeline complete. Data copied into app/src/data.json.")
    print("Next: cd app && npm run build, then copy app/dist/index.html + app/dist/assets to the repo root.")

if __name__ == "__main__":
    main()
