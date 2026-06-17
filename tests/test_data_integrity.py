#!/usr/bin/env python3
"""Data-integrity tests for data/dashboard_data.json. Pure stdlib, runs in CI."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data", "dashboard_data.json")))

def test_blocks_present():
    for b in ["photo", "electro", "oer", "metrics", "leaderboards", "uncertainty", "shap", "defects"]:
        assert b in D, f"missing block: {b}"

def test_photo_count():
    assert len(D["photo"]) >= 120, "expected 120+ photocatalysts"

def test_oer_domain_restricted():
    # main-group, non-OER oxides must be excluded (no descriptor false positives)
    for bad in ["ZnO", "Ag3PO4", "CdO", "SnO2", "In2O3"]:
        assert bad not in D["oer"], f"{bad} must be excluded from OER"
    for good in ["Co3O4", "NiFe LDH", "RuO2"]:
        assert good in D["oer"], f"{good} should be in OER"

def test_oer_leaderboard_real():
    names = {x["name"] for x in D["leaderboards"]["oer"]}
    assert not (names & {"ZnO", "Ag3PO4", "CdO"}), "OER leaderboard must not list non-OER oxides"

def test_uncertainty():
    u = D["uncertainty"]
    assert u.get("her_pm") and u.get("oer_pm"), "missing conformal bands"
    assert u.get("photo_calibrated") is True, "photo probabilities must be calibrated"

def test_honest_metrics():
    assert D["metrics"]["photo_roc_auc"] <= 0.70, "photo ROC-AUC must be the honest grouped value"
    assert D["metrics"]["electro_R2"] >= 0.85, "HER R2 should be strong"

def test_no_em_dash():
    assert "—" not in json.dumps(D, ensure_ascii=False), "no em dash allowed"

def test_band_edges_have_source():
    for k, m in D["photo"].items():
        if m.get("cb") is not None:
            assert m.get("edge_source") in ("literature", "estimated"), f"{k} edge_source missing"

if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f(); print(f"PASS {n}")
    print(f"\nall {len(fns)} data-integrity tests passed")
