"""テスト共通の fixture（設計 §10）。実APIを叩かずモックする。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
GOOD_JSON = (
    '{"dish_name":"のり弁当","total_kcal":700,"protein_g":10,"fat_g":20,'
    '"carb_g":80,"confidence":0.5}'
)


def make_jpeg(path: Path, color: tuple[int, int, int] = (120, 120, 120), size=(64, 64)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG", quality=85)
    return path


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    return make_jpeg(tmp_path / "sample.jpg")


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    """run_one が使う最小 config。derived に小さな JPEG を用意する。"""
    root = tmp_path
    derived = root / "data" / "derived"
    make_jpeg(derived / "IMG_A.jpg", (10, 20, 30))
    make_jpeg(derived / "IMG_B.jpg", (40, 50, 60))
    return {
        "_root": root,
        "providers": {
            "openai": {"base_url": None, "api_key_env": "OPENAI_API_KEY"},
            "aiand": {"base_url_env": "AIAND_BASE_URL", "api_key_env": "AIAND_API_KEY"},
        },
        "pricing": {"fx": {"usd_jpy": "要確認", "ref": "要確認"}},
        "models": [],
        "dishes": [
            {
                "id": "test_dish",
                "label": "テスト",
                "steps": {"S1": ["IMG_A.jpg"], "S2": ["IMG_A.jpg", "IMG_B.jpg"]},
            }
        ],
        "experiment": {
            "temperature": 0,
            "seed": 123,
            "trials": 2,
            "max_json_retries": 2,
            "prompt_version": "v1",
        },
        "image": {"max_dim": 1024, "jpeg_quality": 85},
        "paths": {
            "resources_dir": "../90_resources",
            "derived_dir": "data/derived",
            "logs_dir": "data/logs",
            "results_dir": "data/results",
        },
    }


@pytest.fixture
def jpy_model() -> dict:
    return {
        "id": "m-jpy",
        "provider": "openai",
        "price_input_per_1m": 1.0,
        "price_output_per_1m": 2.0,
        "price_currency": "jpy",
        "price_ref": "ref-jpy",
    }


class FakeClient:
    """chat.completions.create をモックし、呼び出し回数を数える擬似クライアント。

    content: 常に同じ本文を返す。contents: 呼び出しごとに順に返す（末尾以降は最後を反復）。
    exc: 例外を送出する。usage は毎回 prompt/completion=100/20 を返す（積算検証用）。
    """

    def __init__(
        self,
        content: str | None = None,
        exc: Exception | None = None,
        contents: list[str] | None = None,
    ):
        self.calls = 0
        self._content = content
        self._contents = contents
        self._exc = exc
        outer = self

        class _Completions:
            def create(self, **_kwargs):
                idx = outer.calls
                outer.calls += 1
                if outer._exc is not None:
                    raise outer._exc
                if outer._contents is not None:
                    body = outer._contents[min(idx, len(outer._contents) - 1)]
                else:
                    body = outer._content
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=body))],
                    usage=SimpleNamespace(
                        prompt_tokens=100, completion_tokens=20, total_tokens=120
                    ),
                )

        self.chat = SimpleNamespace(completions=_Completions())


@pytest.fixture
def good_client() -> FakeClient:
    return FakeClient(content=GOOD_JSON)


@pytest.fixture
def demo_cfg(tmp_path: Path) -> dict:
    """採点/合成ログ/可視化テスト用のデモ config（truth・単価あり）。"""
    return {
        "_root": tmp_path,
        "pricing": {"fx": {"usd_jpy": 150.0, "ref": "demo"}},
        "models": [
            {
                "id": "m1",
                "provider": "openai",
                "label": "M1",
                "price_input_per_1m": 5.0,
                "price_output_per_1m": 15.0,
                "price_currency": "usd",
                "price_ref": "demo",
                "enabled": True,
            },
            {
                "id": "m2",
                "provider": "aiand",
                "label": "M2",
                "price_input_per_1m": 30.0,
                "price_output_per_1m": 60.0,
                "price_currency": "jpy",
                "price_ref": "demo",
                "enabled": True,
            },
        ],
        "dishes": [
            {
                "id": "d1",
                "label": "料理1",
                "truth": {"total_kcal": 800.0},
                "steps": {
                    "S1": ["a.jpg"],
                    "S2": ["a.jpg", "b.jpg"],
                    "S3": ["a.jpg", "b.jpg", "c.jpg"],
                    "S4": ["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
                },
            }
        ],
        "experiment": {
            "temperature": 0,
            "seed": 123,
            "trials": 3,
            "max_json_retries": 2,
            "prompt_version": "v1",
        },
        "cost_scenario": {"daily_requests": 10000},
        "paths": {
            "logs_dir": "data/logs/demo",
            "results_dir": "data/results/demo",
            "derived_dir": "data/derived",
        },
    }
