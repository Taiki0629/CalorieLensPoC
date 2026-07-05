"""config ロードのテスト（相対 --config でも _root が絶対＝図の出力先が潰れない回帰防止）。"""

from __future__ import annotations

from pathlib import Path

from calorielens.config import load_config


def test_root_is_absolute_with_relative_path(tmp_path: Path, monkeypatch):
    (tmp_path / "config.yaml").write_text("dishes: []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = load_config("config.yaml")  # 相対指定
    assert cfg["_root"].is_absolute()
    assert cfg["_root"] == tmp_path.resolve()
    # _repo_root 相当（.parent）が "." に潰れない
    assert cfg["_root"].parent == tmp_path.resolve().parent
