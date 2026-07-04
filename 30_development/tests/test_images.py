"""画像ユーティリティの単体テスト（AC2 前提の HEIC 変換・manifest 累積）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from calorielens.images import (
    convert_heic_to_jpeg,
    image_ref,
    resolve_step_images,
    sha256_file,
    to_data_url,
)

from .conftest import REPO_ROOT, make_jpeg


def test_resolve_step_images_cumulative(tmp_path: Path):
    derived = tmp_path / "derived"
    steps = {
        "S1": ["a.jpg"],
        "S2": ["a.jpg", "b.jpg"],
        "S3": ["a.jpg", "b.jpg", "c.jpg"],
        "S4": ["a.jpg", "b.jpg", "c.jpg", "d.jpg"],
    }
    for i, key in enumerate(["S1", "S2", "S3", "S4"], start=1):
        paths = resolve_step_images(steps, key, derived)
        assert len(paths) == i
        assert all(p.parent == derived for p in paths)


def test_sha256_and_ref_and_data_url(tmp_path: Path):
    jpg = make_jpeg(tmp_path / "x.jpg")
    digest = sha256_file(jpg)
    assert len(digest) == 64
    ref = image_ref(jpg)
    assert ref["sha256"] == digest and ref["path"] == str(jpg)
    url = to_data_url(jpg)
    assert url.startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize("heic_name", ["IMG_0420.HEIC"])
def test_convert_heic_to_jpeg(tmp_path: Path, heic_name: str):
    src = REPO_ROOT / "90_resources" / heic_name
    if not src.exists():
        pytest.skip(f"原本 HEIC が無い: {src}")
    dst = convert_heic_to_jpeg(src, tmp_path / "out.jpg", max_dim=256, quality=85)
    assert dst.exists()
    from PIL import Image

    with Image.open(dst) as im:
        assert max(im.size) <= 256
