"""モデルに固定させる出力スキーマ（設計 §5）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Estimate(BaseModel):
    """1皿の推定結果。kcal/PFC を最優先で捕捉する（APE 評価が主目的）。

    confidence はモデル自己申告で、スケールや欠損がモデルによって揺れるため寛容に扱う
    （範囲を強制せず、欠損は None）。confidence の不備で kcal/PFC の行ごと脱落させない。
    """

    model_config = ConfigDict(extra="ignore")

    dish_name: str
    total_kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    confidence: float | None = None
