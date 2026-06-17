#!/usr/bin/env python3
"""Engine smoke test (needs the ML env: xgboost, matminer, pymatgen). Run locally."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("H2_MODEL_DIR", os.path.join(ROOT, "models"))
import h2_predictor as hp

def test_engine():
    p = hp.H2Predictor()
    her = p.predict_electro("Pt", "111")
    assert her["predicted_H_energy_eV"] is not None
    oer = p.predict_oer("Co3O4", "110")
    assert oer is not None and "oer_descriptor_eV" in oer
    photo = p.predict_photo("CdS", scavenger="methanol")
    assert photo["performance_tier"] in ("low", "moderate", "high", "exceptional")
    print("engine smoke OK:", her["predicted_H_energy_eV"], oer["oer_descriptor_eV"], photo["performance_tier"])

if __name__ == "__main__":
    test_engine()
