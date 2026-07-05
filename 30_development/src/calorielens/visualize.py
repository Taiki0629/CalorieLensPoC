"""可視化（CAL-10・設計 §4）: scores から図表を生成。日本語は matplotlib-fontja。

配色は dataviz スキルの検証済みカテゴリ配色（slot 1〜5・固定順・色覚安全 worst ΔE 24.2）を
モデル（＝実体）に固定割当し、マーカー形状を二次エンコードに使う（色覚・白黒印刷対策）。単一軸のみ。
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib_fontja  # noqa: E402,F401  日本語フォント設定（import で有効化）

# dataviz reference palette（light）slot 1〜8。モデルへ固定順で割り当てる（順位でなく実体に追従）。
CATEGORICAL = [
    "#2a78d6",
    "#1baf7a",
    "#eda100",
    "#008300",
    "#4a3aa7",
    "#e34948",
    "#e87ba4",
    "#eb6834",
]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"


def _num(v: object) -> float | None:
    """CSV 由来の空文字/None/数値文字列を float|None に正規化。"""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None  # nan/inf は弾く


def _step_key(step: str) -> int:
    try:
        return int(step[1:])
    except (ValueError, IndexError):
        return 0


def model_colors(models: list[str]) -> dict:
    """モデル名→色（ソートした実体順に固定割当。フィルタで順位が変わっても色は不変）。"""
    return {m: CATEGORICAL[i % len(CATEGORICAL)] for i, m in enumerate(sorted(models))}


def model_markers(models: list[str]) -> dict:
    return {m: MARKERS[i % len(MARKERS)] for i, m in enumerate(sorted(models))}


def _new_ax(title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=13)
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.tick_params(colors=MUTED)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(MUTED)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _watermark(fig) -> None:
    fig.text(
        0.5,
        0.5,
        "デモ（合成データ）",
        fontsize=44,
        color="#999999",
        alpha=0.18,
        ha="center",
        va="center",
        rotation=28,
        zorder=10,
    )


def _save(fig, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


def line_ape_vs_steps(
    rows: list[dict],
    out_path: str | Path,
    *,
    dish: str | None = None,
    demo: bool = False,
    colors: dict | None = None,
    markers: dict | None = None,
) -> Path:
    """枚数(S1〜S4)×APE 折れ線（モデル別系列）。dish 指定でその料理のみ。

    colors/markers を渡すと全図で一貫させられる（未指定なら本図のモデル集合から決める）。
    """
    data = [r for r in rows if dish is None or r["dish"] == dish]
    models = sorted({r["model"] for r in data})
    colors = colors or model_colors(models)
    markers = markers or model_markers(models)
    title = "アングル枚数と推定精度（APE）" + (f"／{dish}" if dish else "")
    fig, ax = _new_ax(title, "ステップ（画像の枚数）", "APE（%）＝カロリー誤差")
    for m in models:
        pts = sorted(
            [(r["step"], _num(r["ape_mean"])) for r in data if r["model"] == m],
            key=lambda t: _step_key(t[0]),
        )
        xs = [s for s, y in pts if y is not None]
        ys = [y for s, y in pts if y is not None]
        if xs:
            ax.plot(xs, ys, color=colors[m], marker=markers[m], markersize=7, linewidth=2, label=m)
    if ax.has_data():
        ax.legend(frameon=False, labelcolor=INK)
    if demo:
        _watermark(fig)
    return _save(fig, out_path)


def scatter_cost_ape(
    rows: list[dict],
    out_path: str | Path,
    *,
    demo: bool = False,
    colors: dict | None = None,
    markers: dict | None = None,
) -> Path:
    """コスト×精度 散布（点=モデル×ステップ、色=モデル）。"""
    models = sorted({r["model"] for r in rows})
    colors = colors or model_colors(models)
    markers = markers or model_markers(models)
    fig, ax = _new_ax(
        "コストと精度のトレードオフ", "1リクエスト平均コスト（円）", "APE（%）＝カロリー誤差"
    )
    for m in models:
        xs, ys = [], []
        for r in rows:
            if r["model"] != m:
                continue
            c, a = _num(r["cost_jpy_mean"]), _num(r["ape_mean"])
            if c is not None and a is not None:
                xs.append(c)
                ys.append(a)
        if xs:
            ax.scatter(
                xs,
                ys,
                color=colors[m],
                marker=markers[m],
                s=70,
                edgecolors=SURFACE,
                linewidths=1.2,
                label=m,
            )
    if ax.has_data():
        ax.legend(frameon=False, labelcolor=INK)
    if demo:
        _watermark(fig)
    return _save(fig, out_path)


def _fmt(v: object, spec: str) -> str:
    n = _num(v)
    return format(n, spec) if n is not None else "—"


def _render_table(
    headers: list[str],
    table_rows: list[list[str]],
    title: str,
    out_path: str | Path,
    *,
    demo: bool = False,
) -> Path:
    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(headers)), 0.5 + 0.4 * (len(table_rows) + 1)))
    fig.patch.set_facecolor(SURFACE)
    ax.axis("off")
    ax.set_title(title, color=INK, fontsize=13, pad=12)
    tbl = ax.table(cellText=table_rows, colLabels=headers, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.4)
    for (r, _c), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_text_props(color=INK)  # IPAexGothic は bold 無し。背景色で見出しを区別
            cell.set_facecolor("#f0efec")
        else:
            cell.set_text_props(color=INK)
    if demo:
        _watermark(fig)
    return _save(fig, out_path)


def ranking_rows(summary: list[dict]) -> list[dict]:
    """ランキング用に並べ替え: APE平均 昇順 → コスト 昇順 → モデル名（APE 無しは末尾）。"""

    def key(r: dict):
        ape = _num(r.get("ape_mean"))
        cost = _num(r.get("cost_jpy_mean"))
        return (
            ape is None,
            ape if ape is not None else 0.0,
            cost if cost is not None else 0.0,
            r["model"],
        )

    return sorted(summary, key=key)


def ranking_table(summary: list[dict], out_png: str | Path, *, demo: bool = False) -> Path:
    ordered = ranking_rows(summary)
    headers = ["順位", "モデル", "APE平均(%)", "料理名正解率", "速度(ms)", "コスト(円/req)"]
    trows = []
    for i, r in enumerate(ordered, start=1):
        acc = _num(r.get("name_accuracy"))
        trows.append(
            [
                str(i),
                r["model"],
                _fmt(r.get("ape_mean"), ".1f"),
                f"{acc * 100:.0f}%" if acc is not None else "—",
                _fmt(r.get("latency_ms_mean"), ".0f"),
                _fmt(r.get("cost_jpy_mean"), ".4f"),
            ]
        )
    return _render_table(headers, trows, "モデル別ランキング", out_png, demo=demo)


def daily_cost_rows(score_rows: list[dict], daily_requests: int) -> list[dict]:
    """(model, step) 単位で 1日あたりコストを算出（daily_jpy = cost/req × req数）。"""
    out = []
    for r in sorted(score_rows, key=lambda x: (x["model"], _step_key(x["step"]))):
        cost = _num(r.get("cost_jpy_mean"))
        out.append(
            {
                "model": r["model"],
                "step": r["step"],
                "cost_jpy_mean": cost if cost is not None else "",
                "daily_requests": daily_requests,
                "daily_jpy": (cost * daily_requests) if cost is not None else "",
            }
        )
    return out


def daily_cost_table(
    score_rows: list[dict], daily_requests: int, out_png: str | Path, *, demo: bool = False
) -> Path:
    rows = daily_cost_rows(score_rows, daily_requests)
    headers = ["モデル", "ステップ", "コスト(円/req)", "リクエスト/日", "コスト(円/日)"]
    trows = [
        [
            r["model"],
            r["step"],
            _fmt(r["cost_jpy_mean"], ".4f"),
            f"{daily_requests:,}",
            _fmt(r["daily_jpy"], ",.0f"),
        ]
        for r in rows
    ]
    return _render_table(
        headers, trows, f"1日あたりコスト試算（{daily_requests:,} req/日）", out_png, demo=demo
    )
