"""runner.run_one の end-to-end 単体テスト（モック応答）。AC2〜4 の経路を検証。"""

from __future__ import annotations

from calorielens.runner import count_conditions, iter_conditions, run_one

from .conftest import GOOD_JSON, FakeClient


def test_run_one_ok(cfg, jpy_model, good_client):
    rec = run_one(cfg, "test_dish", "S2", jpy_model, 1, "run1", client=good_client)
    assert rec["status"] == "ok"
    assert rec["n_images"] == 2
    assert rec["attempts"] == 1
    assert rec["parsed"]["dish_name"] == "のり弁当"
    assert len(rec["image_refs"]) == 2
    assert all(len(r["sha256"]) == 64 for r in rec["image_refs"])
    assert rec["cost_jpy"] is not None and rec["cost_jpy"] > 0
    assert "api_key" not in rec


def test_image_refs_are_relative(cfg, jpy_model, good_client):
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=good_client)
    path = rec["image_refs"][0]["path"]
    # 相対パス（絶対パス＝ホーム名混入を避ける・設計 §8）
    assert path == "data/derived/IMG_A.jpg"
    assert not path.startswith("/")


def test_retry_then_ok_accumulates_cost_and_attempts(cfg, jpy_model):
    # 初回は不正JSON→リトライで成功。usage は2回分積算され、attempts=2
    client = FakeClient(contents=["not json", GOOD_JSON])
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=client)
    assert rec["status"] == "ok"
    assert rec["attempts"] == 2
    assert client.calls == 2
    # 2回分: input=200, output=40 → jpy cost = 200/1e6*1 + 40/1e6*2
    assert rec["usage"]["input_tokens"] == 200
    assert rec["usage"]["output_tokens"] == 40
    expected = 200 / 1e6 * 1.0 + 40 / 1e6 * 2.0
    assert abs(rec["cost_jpy"] - expected) < 1e-12


def test_run_one_parse_error_retries(cfg, jpy_model):
    client = FakeClient(content="これはJSONではありません")
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=client)
    assert rec["status"] == "parse_error"
    assert rec["error"]
    # max_json_retries=2 → 初回＋リトライ2回 = 3 回呼ぶ
    assert client.calls == 3
    assert rec["attempts"] == 3
    # 3回分課金が積算される
    assert rec["usage"]["input_tokens"] == 300


def test_run_one_api_error(cfg, jpy_model):
    client = FakeClient(exc=RuntimeError("boom"))
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=client)
    assert rec["status"] == "api_error"
    assert client.calls == 1
    assert rec["attempts"] == 0


def test_run_one_vision_unsupported(cfg, jpy_model):
    client = FakeClient(exc=RuntimeError("this model does not support image input"))
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=client)
    assert rec["status"] == "vision_unsupported"


def test_run_one_no_key_no_client(cfg, jpy_model, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rec = run_one(cfg, "test_dish", "S1", jpy_model, 1, "run1", client=None)
    assert rec["status"] == "api_error"
    assert "API key not set" in rec["error"]


def test_run_one_aiand_base_url_required(cfg, monkeypatch):
    # api_key はあるが base_url 未設定 → OpenAI へ誤送信せず明示エラー
    monkeypatch.setenv("AIAND_API_KEY", "dummy")
    monkeypatch.delenv("AIAND_BASE_URL", raising=False)
    aiand_model = {"id": "m", "provider": "aiand", "price_currency": "jpy"}
    rec = run_one(cfg, "test_dish", "S1", aiand_model, 1, "run1", client=None)
    assert rec["status"] == "api_error"
    assert "base_url not set" in rec["error"]


def test_iter_and_count_conditions(cfg, jpy_model):
    models = [jpy_model]
    n = count_conditions(cfg, models=models)
    # 1 dish × 2 steps × 1 model × trials(2) = 4
    assert n == 4
    conds = list(iter_conditions(cfg, models=models))
    assert len(conds) == 4
    assert {c[1] for c in conds} == {"S1", "S2"}
