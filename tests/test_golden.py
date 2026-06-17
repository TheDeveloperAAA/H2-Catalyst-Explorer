#!/usr/bin/env python3
"""
Golden-value regression tests.

Invariant/smoke tests prove the data is well-formed; they cannot notice a model
that silently went wrong. These pin a few anchor predictions to their known-good
chemistry, so a bad retrain (wrong target, leaked split, broken featurizer, a
re-introduced provenance bug) trips CI instead of shipping. Bands are wide enough
to absorb honest seed-to-seed drift but tight enough to catch a real regression.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data", "dashboard_data.json")))


def test_golden_pt_her():
    # Pt(111) binds H* slightly too strongly: dG_H near -0.46 eV, mid-pack, not the
    # textbook "best HER metal" myth. This is the headline honesty claim of the tool.
    pt = D["electro"]["Pt"]
    assert -0.65 <= pt["energy_eV"] <= -0.25, f"Pt dG_H drifted to {pt['energy_eV']}"
    assert 40 <= pt["score"] <= 70, f"Pt HER score drifted to {pt['score']}"
    assert "strong" in pt["verdict"].lower(), "Pt should read as too-strong binding"


def test_golden_her_ordering():
    # The headline honesty claim: the model rediscovers MoS2 (near-thermoneutral, dG_H
    # ~0) as the top HER catalyst and places Pt mid-pack, not at the top.
    e = D["electro"]
    assert e["MoS2"]["score"] > e["Pt"]["score"], "MoS2 should outrank Pt for HER"
    assert abs(e["MoS2"]["energy_eV"]) < 0.20, f"MoS2 dG_H should be near 0, got {e['MoS2']['energy_eV']}"


def test_golden_oer_anchors():
    # Literature overpotentials for the canonical OER benchmarks must be carried through.
    o = D["oer"]
    assert o["IrO2"]["lit_eta_mV"] == 320, "IrO2 literature eta changed"
    assert o["RuO2"]["lit_eta_mV"] == 280, "RuO2 literature eta changed"


def test_golden_oer_descriptor_band_wider():
    # The descriptor is a DIFFERENCE of two energies, so its band must exceed the
    # per-energy conformal band. If they are equal, the propagation regressed.
    u = D["uncertainty"]
    assert u["oer_desc_pm"] > u["oer_pm"], "descriptor band must be wider than per-energy band"
    assert 2.0 <= u["oer_desc_pm"] <= 5.0, f"descriptor band implausible: {u['oer_desc_pm']}"


def test_golden_conformal_coverage_validated():
    # The "90%" bands must be empirically validated on a disjoint test fold, not
    # asserted. Coverage should land near 0.90 (allow sampling slack).
    u = D["uncertainty"]
    assert 0.80 <= u["her_coverage"] <= 0.97, f"HER coverage off target: {u.get('her_coverage')}"
    assert 0.78 <= u["oer_coverage"] <= 0.97, f"OER coverage off target: {u.get('oer_coverage')}"


def test_golden_calibration_out_of_sample():
    # Calibration must be fit on held-out rows the model never trained on.
    u = D["uncertainty"]
    assert u.get("calib_out_of_sample") is True, "photo calibration must be out-of-sample"
    assert u.get("calib_n", 0) >= 300, "too few held-out calibration rows"


def test_golden_oer_model_honestly_weak():
    # Guard against the leakage coming back: leak-free, the OER regressor is weak.
    # If oer_cv_R2 climbs back toward the old inflated 0.86, the group key regressed.
    m = D["metrics"]
    assert m["oer_cv_R2"] < 0.78, f"OER CV R2 implausibly high ({m['oer_cv_R2']}); leakage may be back"
    arm = m.get("oer_arm_R2", {})
    assert "O*" in arm and "OH*" in arm, "per-arm R2 must be recorded"


def test_golden_oer_reconciliation():
    # RuO2 is a benchmark OER catalyst (lit eta 280 mV) that the weak model rates
    # "Poor"; the data must flag the disagreement and keep literature primary.
    ru = D["oer"]["RuO2"]
    assert ru["lit_eta_mV"] == 280
    assert ru["model_disagrees"] is True, "RuO2 model/lit disagreement must be flagged"
    assert "Excellent" in (ru.get("verdict_primary") or ""), "RuO2 should read excellent from literature"
    assert ru.get("confidence") == "literature-anchored"


def test_golden_water_overpotential_buffer():
    # Thin-margin straddles must NOT be called "Yes". WS2 clears the O2/H2O line by
    # only ~0.02 V, so it must be 'marginal', not a confident splitter.
    assert D["photo"]["WS2"]["water_verdict"] == "marginal", "WS2 should be marginal, not Yes"
    # and a genuine straddler with headroom stays yes
    assert D["photo"]["SrTiO3"]["water_verdict"] in ("yes", "marginal")


def test_golden_gap_provenance_not_collapsed():
    # Regression guard for the provenance feedback loop: the curated CSV used to get
    # relabelled so ~124/127 read "curated". True provenance has many literature gaps
    # and curated must NOT dominate.
    src = {}
    for m in D["photo"].values():
        s = m.get("gap_source", "?")
        src[s] = src.get(s, 0) + 1
    lit = src.get("literature", 0)
    cur = src.get("curated", 0)
    assert lit >= 40, f"too few literature-sourced gaps ({lit}); provenance loop may be back"
    assert cur < 80, f"curated gaps dominate ({cur}); provenance loop may be back"


def test_golden_oer_has_both_anchored_and_model_only():
    # Some OER entries are literature-anchored, some are model-only (lower confidence).
    # Both populations must exist so the UI confidence split stays meaningful.
    anchored = sum(1 for v in D["oer"].values() if v.get("lit_eta_mV"))
    model_only = sum(1 for v in D["oer"].values() if not v.get("lit_eta_mV"))
    assert anchored >= 15, f"too few literature-anchored OER ({anchored})"
    assert model_only >= 5, f"expected some model-only OER, got {model_only}"


def test_golden_photo_tio2_reasonable():
    # TiO2 is a real but UV-only workhorse: a sane mid-range "worth synthesizing" prob,
    # never a saturated 0 or 1 after calibration.
    p = D["photo"]["TiO2"]["combos"]["methanol|true"]["promising"]
    assert 0.15 <= p <= 0.85, f"TiO2 promising prob implausible: {p}"


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f(); print(f"PASS {n}")
    print(f"\nall {len(fns)} golden-value tests passed")
