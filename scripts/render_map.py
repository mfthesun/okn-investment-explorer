"""Схема координат пилота: python scripts/render_map.py (matplotlib)."""

import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]


def render(output=None):
    points = json.loads((ROOT / "data/reference/coordinates.json").read_text())[
        "points"
    ]
    fig, ax = plt.subplots(figsize=(6, 8))
    for oid, p in points.items():
        # Локальное равнопромежуточное приближение при 60°N, километры.
        x = (p["lon"] - 30.2) * 111.32 * 0.5
        y = (p["lat"] - 59.9) * 111.32
        ax.scatter(x, y, c="#235b4b", s=65)
        ax.annotate(
            oid,
            (x, y),
            xytext=(8, -15 if oid == "490" else 9),
            textcoords="offset points",
        )
    ax.set_aspect("equal")
    ax.set_xlim(-1, 13)
    ax.set_ylim(-2, 28)
    ax.set_xlabel("Восточнее 30,20° в. д., км")
    ax.set_ylabel("Севернее 59,90° с. ш., км")
    ax.plot([0, 5], [-0.8, -0.8], c="#203b36", lw=3)
    ax.text(2.5, -1.5, "5 км", ha="center")
    ax.annotate(
        "С", xy=(11, 26), xytext=(11, 23), arrowprops={"arrowstyle": "->"}, ha="center"
    )
    ax.legend(
        handles=[
            Line2D(
                [0],
                [0],
                marker="o",
                color="white",
                markerfacecolor="#235b4b",
                label="Пилотный объект · номер КГИОП",
            )
        ],
        loc="upper left",
        facecolor="white",
        framealpha=1,
    )
    ax.grid(alpha=0.15)
    fig.text(
        0.05,
        0.025,
        "Источник: data/raw/dataset.xlsx, срез НИР2. Проверка: 03.11.2026.\nСхема без подложки; точность на местности не подтверждена.",
        fontsize=8,
    )
    fig.subplots_adjust(bottom=0.13)
    output = Path(output or ROOT / "docs/screenshots/pilot-map.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output


if __name__ == "__main__":
    print(render())
