"""コスト計算と通貨正規化の単体テスト（設計 §7.1）。"""

from __future__ import annotations

from calorielens.cost import compute_cost_jpy, price_ref

USAGE = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}


def test_jpy_model_native():
    model = {"price_input_per_1m": 1.0, "price_output_per_1m": 2.0, "price_currency": "jpy"}
    assert compute_cost_jpy(USAGE, model, {}) == 3.0


def test_usd_model_uses_fx():
    model = {"price_input_per_1m": 1.0, "price_output_per_1m": 2.0, "price_currency": "usd"}
    fx = {"usd_jpy": 150.0}
    assert compute_cost_jpy(USAGE, model, fx) == 3.0 * 150.0


def test_unconfirmed_price_returns_none():
    model = {
        "price_input_per_1m": "要確認",
        "price_output_per_1m": "要確認",
        "price_currency": "usd",
    }
    assert compute_cost_jpy(USAGE, model, {"usd_jpy": 150.0}) is None


def test_usd_without_fx_returns_none():
    model = {"price_input_per_1m": 1.0, "price_output_per_1m": 2.0, "price_currency": "usd"}
    assert compute_cost_jpy(USAGE, model, {"usd_jpy": "要確認"}) is None


def test_no_usage_returns_none():
    model = {"price_input_per_1m": 1.0, "price_output_per_1m": 2.0, "price_currency": "jpy"}
    assert compute_cost_jpy(None, model, {}) is None


def test_price_ref_appends_fx_for_usd():
    model = {"price_currency": "usd", "price_ref": "openai-pricing 2026-07-05"}
    ref = price_ref(model, {"ref": "fx-src 2026-07-05"})
    assert "fx=" in ref and "openai-pricing" in ref
