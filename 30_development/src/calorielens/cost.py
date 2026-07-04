"""コスト計算と通貨正規化（設計 §7.1）。単価×usage を JPY に揃える。数値手打ち禁止の要。"""

from __future__ import annotations


def _is_num(v: object) -> bool:
    """bool を除く数値か（`要確認` 文字列や None を弾く）。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compute_cost_jpy(usage: dict | None, model_cfg: dict, fx: dict) -> float | None:
    """usage×config単価→JPY。単価・為替が未確定（要確認）や usage 無し・通貨不明なら None。"""
    if not usage:
        return None
    pin = model_cfg.get("price_input_per_1m")
    pout = model_cfg.get("price_output_per_1m")
    if not (_is_num(pin) and _is_num(pout)):
        return None
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    native = input_tokens / 1e6 * pin + output_tokens / 1e6 * pout
    currency = str(model_cfg.get("price_currency") or "").lower()
    if currency == "usd":
        rate = fx.get("usd_jpy")
        if not _is_num(rate):
            return None
        return native * rate
    if currency == "jpy":
        return native
    return None  # 通貨不明は静かに誤らせず None


def price_ref(model_cfg: dict, fx: dict) -> str | None:
    """ログに残す単価の出典。USD建てなら為替の出典も連結する。"""
    ref = model_cfg.get("price_ref")
    if str(model_cfg.get("price_currency") or "").lower() == "usd":
        return f"{ref}; fx={fx.get('ref')}"
    return ref
