"""画像ユーティリティ（設計 §8）。HEIC→JPEG 変換・sha256・data URL・manifest 解決。"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pillow_heif
from PIL import Image, ImageDraw, ImageOps

pillow_heif.register_heif_opener()


def convert_heic_to_jpeg(
    src: str | Path, dst: str | Path, max_dim: int = 1024, quality: int = 85
) -> Path:
    """HEIC を長辺 max_dim・quality の JPEG に決定的に変換する。EXIF 向きを正立に補正する。"""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)  # iPhone 等の回転情報を実ピクセルに反映（横倒し防止）
    im = im.convert("RGB")
    im.thumbnail((max_dim, max_dim))
    im.save(dst, "JPEG", quality=quality)
    return dst


def sha256_file(path: str | Path) -> str:
    """ファイル内容の SHA-256（16進）。"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_ref(path: str | Path, base: str | Path | None = None) -> dict:
    """ログ用の画像参照 {path, sha256}（生 base64 は含めない）。

    base を渡すと base からの相対パスで記録する（ホーム名混入・非再現を避ける。設計 §8）。
    """
    path = Path(path)
    rel = path
    if base is not None:
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = path
    return {"path": str(rel), "sha256": sha256_file(path)}


def to_data_url(path: str | Path) -> str:
    """JPEG を data URL（base64）にする。送信時のみ使用しログには残さない。"""
    data = Path(path).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def resolve_step_images(steps: dict, step: str, derived_dir: str | Path) -> list[Path]:
    """steps[step] のファイル名を derived_dir 配下の累積パス列に解決する。"""
    derived_dir = Path(derived_dir)
    return [derived_dir / name for name in steps[step]]


def build_contact_sheet(
    entries: list[tuple[str, str | Path]],
    dst: str | Path,
    *,
    cols: int = 3,
    cell: tuple[int, int] = (360, 300),
    label_h: int = 34,
    pad: int = 8,
) -> Path:
    """(ラベル, jpegパス) の列からラベル付きコンタクトシートを生成する（俯角順の目視確認用）。"""
    dst = Path(dst)
    cell_w, cell_h = cell
    rows = (len(entries) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for i, (label, path) in enumerate(entries):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * (cell_h + label_h)
        thumb = Image.open(path).convert("RGB")
        thumb.thumbnail((cell_w - 2 * pad, cell_h - 2 * pad))
        sheet.paste(thumb, (x0 + pad, y0 + label_h + pad))
        draw.rectangle(
            [x0, y0, x0 + cell_w - 1, y0 + cell_h + label_h - 1], outline=(180, 180, 180)
        )
        draw.text((x0 + pad, y0 + 8), label, fill=(20, 20, 20))
    dst.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dst, "JPEG", quality=88)
    return dst
