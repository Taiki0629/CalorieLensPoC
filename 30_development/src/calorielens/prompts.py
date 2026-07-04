"""プロンプトの版管理（設計 §4）。複数枚は「同一料理の別アングル」である旨を明示する。"""

from __future__ import annotations

PROMPTS: dict[str, str] = {
    "v1": (
        "あなたは料理写真から栄養を推定する専門家です。\n"
        "与えられた画像は【同一の1皿の料理】を異なるアングルから撮影したものです"
        "（画像が複数枚でも料理は1つ。別々の料理として合算しないこと）。\n"
        "その料理全体について、料理名・推定総カロリー(kcal)・タンパク質(g)・脂質(g)・"
        "炭水化物(g)・確信度(0〜1)を推定してください。\n"
        "出力は次のJSONオブジェクトのみ（前後に説明文やコードフェンスを付けない）:\n"
        '{"dish_name": string, "total_kcal": number, "protein_g": number, '
        '"fat_g": number, "carb_g": number, "confidence": number}'
    ),
}


def get_prompt(version: str) -> str:
    """指定版のプロンプト文字列を返す。未知の版は KeyError。"""
    return PROMPTS[version]
