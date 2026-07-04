"""client の単体テスト（usage 名マッピング・messages 構築）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from calorielens.client import build_messages, map_usage

from .conftest import make_jpeg


def test_map_usage_from_sdk_object():
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    out = map_usage(usage)
    assert out == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}


def test_map_usage_from_dict():
    # ai& の形状が dict の可能性（設計 §2.1 未確認パス）
    out = map_usage({"prompt_tokens": 5, "completion_tokens": 7})
    assert out["input_tokens"] == 5 and out["output_tokens"] == 7
    assert out["total_tokens"] == 12  # 欠損 total は補完


def test_map_usage_prefers_openai_native_names():
    usage = SimpleNamespace(input_tokens=1, output_tokens=2, total_tokens=3)
    assert map_usage(usage)["input_tokens"] == 1


def test_map_usage_none():
    assert map_usage(None) is None
    assert map_usage(SimpleNamespace()) is None


def test_build_messages_structure(tmp_path: Path):
    a = make_jpeg(tmp_path / "a.jpg")
    b = make_jpeg(tmp_path / "b.jpg")
    msgs = build_messages("prompt text", [a, b])
    assert len(msgs) == 1
    content = msgs[0]["content"]
    assert content[0] == {"type": "text", "text": "prompt text"}
    images = [c for c in content if c["type"] == "image_url"]
    assert len(images) == 2
    assert all(c["image_url"]["url"].startswith("data:image/jpeg;base64,") for c in images)
