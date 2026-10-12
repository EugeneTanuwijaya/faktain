"""Unit tests for verdict consistency + status normalization (no network)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.llm_service import (
    _enforce_verdict_consistency,
    _normalize_claim_status,
)


def test_status_normalization():
    assert _normalize_claim_status("BELUM TERVERIFIKASI") == "TIDAK DAPAT DIVERIFIKASI"
    assert _normalize_claim_status("Terkonfirmasi") == "TERKONFIRMASI"
    assert _normalize_claim_status("DIBANTAH") == "DIBANTAH"
    assert _normalize_claim_status("salah") == "DIBANTAH"
    assert _normalize_claim_status("") == "TIDAK DAPAT DIVERIFIKASI"
    assert _normalize_claim_status("unverified") == "TIDAK DAPAT DIVERIFIKASI"


def test_peripheral_unverified_does_not_drag_core_credible():
    """The reported bug: core claims confirmed, one peripheral detail
    unverifiable -> should stay KREDIBEL, not drop to PERLU DICEK."""
    result = {
        "confidence_score": 85,
        "verdict": "KREDIBEL",
        "reasoning": "Aksi mahasiswa terkonfirmasi.",
        "verified_claims": [
            {"claim": "Ada demo mahasiswa di Jakarta", "status": "TERKONFIRMASI", "explanation": "", "is_core": True},
            {"claim": "Jumlah personel 3.099 vs 3.651+500", "status": "BELUM TERVERIFIKASI", "explanation": "", "is_core": False},
        ],
    }
    _enforce_verdict_consistency(result)
    assert result["verdict"] == "KREDIBEL", result["verdict"]
    assert 75 <= result["confidence_score"] <= 100
    # peripheral status normalized for the UI
    assert result["verified_claims"][1]["status"] == "TIDAK DAPAT DIVERIFIKASI"


def test_debunked_core_forces_hoax():
    result = {
        "confidence_score": 90,
        "verdict": "KREDIBEL",
        "reasoning": "",
        "verified_claims": [
            {"claim": "X terjadi", "status": "DIBANTAH", "explanation": "", "is_core": True},
        ],
    }
    _enforce_verdict_consistency(result)
    assert result["verdict"] == "KEMUNGKINAN HOAKS"
    assert result["confidence_score"] <= 30


def test_no_core_confirmed_downgrades():
    result = {
        "confidence_score": 80,
        "verdict": "KREDIBEL",
        "reasoning": "",
        "verified_claims": [
            {"claim": "X terjadi", "status": "BELUM TERVERIFIKASI", "explanation": "", "is_core": True},
        ],
    }
    _enforce_verdict_consistency(result)
    assert result["verdict"] == "PERLU DICEK"
    assert 40 <= result["confidence_score"] <= 60


if __name__ == "__main__":
    test_status_normalization()
    test_peripheral_unverified_does_not_drag_core_credible()
    test_debunked_core_forces_hoax()
    test_no_core_confirmed_downgrades()
    print("All verdict-logic tests passed.")
