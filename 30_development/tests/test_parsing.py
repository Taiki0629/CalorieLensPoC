"""パース／リトライの単体テスト（AC3）。"""

from __future__ import annotations

import json

from calorielens.parsing import extract_json, parse_estimate


def _obj(**over) -> dict:
    base = {
        "dish_name": "x",
        "total_kcal": 700,
        "protein_g": 10,
        "fat_g": 20,
        "carb_g": 80,
        "confidence": 0.5,
    }
    base.update(over)
    return base


def _json(**over) -> str:
    return json.dumps(_obj(**over), ensure_ascii=False)


def test_clean_json():
    est, err = parse_estimate(_json(dish_name="x", total_kcal=700))
    assert err is None
    assert est.dish_name == "x"
    assert est.total_kcal == 700.0


def test_fenced_json():
    text = f"推定結果です。\n```json\n{_json(dish_name='y')}\n```\n以上。"
    est, err = parse_estimate(text)
    assert err is None
    assert est.dish_name == "y"


def test_surrounded_text():
    text = f"ここに結果: {_json(dish_name='z', carb_g=40)} 完了"
    est, err = parse_estimate(text)
    assert err is None
    assert est.carb_g == 40.0


def test_trailing_brace_text_after_json():
    # JSON の後ろに {} を含む地の文があっても先頭オブジェクトを取れる（raw_decode）
    text = f"{_json(dish_name='w')} 補足: {{重要}}"
    est, err = parse_estimate(text)
    assert err is None
    assert est.dish_name == "w"


def test_two_objects_takes_first():
    text = f"{_json(dish_name='first')} {_json(dish_name='second')}"
    obj = extract_json(text)
    assert obj is not None and obj["dish_name"] == "first"


def test_string_numbers_coerced():
    # 文字列の数値も数値型に coercion される
    est, err = parse_estimate(_json(total_kcal="720"))
    assert err is None
    assert est.total_kcal == 720.0


def test_invalid_returns_reason():
    est, err = parse_estimate("これはJSONではありません")
    assert est is None
    assert err and "no JSON" in err


def test_confidence_out_of_range_is_lenient():
    # confidence は寛容（範囲外でも kcal/PFC を捨てない）
    est, err = parse_estimate(_json(confidence=85))
    assert err is None
    assert est.total_kcal == 700.0
    assert est.confidence == 85.0


def test_confidence_missing_ok():
    obj = _obj()
    del obj["confidence"]
    est, err = parse_estimate(json.dumps(obj))
    assert err is None
    assert est.confidence is None


def test_missing_required_kcal_is_error():
    obj = _obj()
    del obj["total_kcal"]
    est, err = parse_estimate(json.dumps(obj))
    assert est is None
    assert err and "validation" in err


def test_extract_json_none_on_empty():
    assert extract_json("") is None
