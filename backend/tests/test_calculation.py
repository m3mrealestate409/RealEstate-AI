"""Unit tests for the deterministic calculation engine (Constitution §18)."""
from app.services.calculation import run_calculation
from app.services.calculation.engine import emi, payment_schedule, roi, total_cost


def test_total_cost_per_sqft():
    r = total_cost(base_price=9000, area=1000, plc=300000, gst_percent=5)
    # base = 9,000,000 ; +PLC 300,000 => subtotal 9,300,000 ; GST 5% => 465,000
    assert r["subtotal"] == 9300000.0
    assert r["gst_amount"] == 465000.0
    assert r["total"] == 9765000.0


def test_payment_schedule_splits_correctly():
    r = payment_schedule(
        total_amount=10000000,
        milestones=[{"label": "Booking", "percent": 10}, {"label": "Rest", "percent": 90}],
    )
    assert r["schedule"][0]["amount"] == 1000000.0
    assert r["schedule"][1]["cumulative"] == 10000000.0


def test_emi_known_value():
    # 10,00,000 @ 8% for 120 months ~ 12,132.76
    r = emi(principal=1000000, annual_rate=8, tenure_months=120)
    assert abs(r["emi"] - 12132.76) < 0.5
    assert r["total_interest"] > 0


def test_roi_and_cagr():
    r = roi(investment=1000000, current_value=1500000, years=5)
    assert r["roi_percent"] == 50.0
    assert "cagr_percent" in r


def test_registry_dispatch():
    r = run_calculation("gst", {"taxable_value": 1000, "rate": 5})
    assert r["gst_amount"] == 50.0
