# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Generate the source-grounding and implementation-boundary concept figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "manuscript"

INK = "#172333"
MUTED = "#516070"
GRID = "#D8DEE5"
SOURCE = "#EEF1F4"
SPAN = "#DCEBF7"
EVIDENCE = "#D9EFE7"
LINK = "#FBE4C6"
ASSERTION = "#275D7A"
CONTEXT = "#E9E2F4"
WORKFLOW = "#E7EEF5"
EXPORT = "#DDECE8"
FUTURE = "#F6F7F8"


def add_box(
    ax,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    facecolor: str,
    edgecolor: str = MUTED,
    textcolor: str = INK,
    linestyle: str = "-",
    linewidth: float = 1.2,
    fontsize: float = 9.0,
    weight: str = "normal",
    radius: float = 0.02,
):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        linestyle=linestyle,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        color=textcolor,
        fontsize=fontsize,
        fontweight=weight,
        linespacing=1.25,
    )
    return patch


def add_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = MUTED,
    linestyle: str = "-",
    linewidth: float = 1.3,
    label: str | None = None,
    label_offset: tuple[float, float] = (0.0, 0.0),
    connectionstyle: str = "arc3",
):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=linewidth,
        linestyle=linestyle,
        color=color,
        connectionstyle=connectionstyle,
        shrinkA=2,
        shrinkB=2,
    )
    ax.add_patch(arrow)
    if label:
        x = (start[0] + end[0]) / 2 + label_offset[0]
        y = (start[1] + end[1]) / 2 + label_offset[1]
        ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=7.5,
            color=MUTED,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2},
        )
    return arrow


def build_figure():
    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "csag-concept-figure",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 5.2), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.patch.set_facecolor("white")
    for ax in axes:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()

    ax_a, ax_b = axes
    ax_a.text(0.01, 0.975, "A", fontsize=16, fontweight="bold", color=INK, va="top")
    ax_b.text(0.01, 0.975, "B", fontsize=16, fontweight="bold", color=INK, va="top")

    add_box(
        ax_a,
        0.06,
        0.78,
        0.28,
        0.12,
        "Source\nmanuscript text\nfigure · table",
        facecolor=SOURCE,
        weight="bold",
    )
    add_box(
        ax_a,
        0.52,
        0.76,
        0.33,
        0.16,
        "TextSpan\ndocument · section\ncharacter offsets",
        facecolor=SPAN,
        weight="bold",
    )
    add_arrow(ax_a, (0.34, 0.84), (0.52, 0.84), label="anchors")

    add_box(
        ax_a,
        0.04,
        0.40,
        0.22,
        0.16,
        "EvidenceItem\nresult or\nobservation",
        facecolor=EVIDENCE,
        fontsize=8.4,
        weight="bold",
    )
    add_box(
        ax_a,
        0.31,
        0.40,
        0.20,
        0.16,
        "EvidenceLink\npolarity ·\nstrength",
        facecolor=LINK,
        fontsize=8.4,
        weight="bold",
    )
    add_box(
        ax_a,
        0.56,
        0.37,
        0.24,
        0.22,
        "Assertion\nclaim · criticality\nfalsification\ncriterion",
        facecolor=ASSERTION,
        edgecolor=ASSERTION,
        textcolor="white",
        weight="bold",
    )
    add_box(
        ax_a,
        0.61,
        0.08,
        0.28,
        0.17,
        "Context\norganism · assay\nenvironment",
        facecolor=CONTEXT,
        weight="bold",
    )

    add_arrow(ax_a, (0.26, 0.48), (0.31, 0.48))
    add_arrow(ax_a, (0.51, 0.48), (0.56, 0.48))
    add_arrow(ax_a, (0.68, 0.37), (0.74, 0.25), label="scoped by", label_offset=(0.08, 0.0))
    add_arrow(
        ax_a,
        (0.61, 0.76),
        (0.18, 0.56),
        label="grounds",
        label_offset=(-0.05, 0.03),
        connectionstyle="arc3,rad=0.10",
    )
    add_arrow(
        ax_a,
        (0.72, 0.76),
        (0.71, 0.59),
        label="grounds",
        label_offset=(0.06, 0.0),
    )

    workflow_boxes = [
        (0.02, 0.77, 0.23, "PDF /\nMarkdown", SOURCE),
        (0.37, 0.77, 0.25, "ingest · scaffold\ncurate CSAG", WORKFLOW),
        (0.74, 0.77, 0.23, "validate\nreport · lint", WORKFLOW),
        (0.17, 0.57, 0.29, "export\nJSON · RO-Crate\nRDF", EXPORT),
        (0.58, 0.57, 0.30, "human review\naccept · revise", SOURCE),
    ]
    for x, y, width, text, color in workflow_boxes:
        add_box(
            ax_b,
            x,
            y,
            width,
            0.13,
            text,
            facecolor=color,
            fontsize=9.0,
            weight="bold",
        )
    add_arrow(ax_b, (0.25, 0.835), (0.37, 0.835))
    add_arrow(ax_b, (0.62, 0.835), (0.74, 0.835))
    add_arrow(
        ax_b,
        (0.84, 0.77),
        (0.42, 0.70),
        connectionstyle="arc3,rad=0.18",
    )
    add_arrow(ax_b, (0.46, 0.635), (0.58, 0.635))

    add_box(
        ax_b,
        0.12,
        0.34,
        0.26,
        0.12,
        "Agent / curator\nread · revise",
        facecolor=SOURCE,
        weight="bold",
    )
    add_box(
        ax_b,
        0.60,
        0.34,
        0.26,
        0.12,
        "CSAG + handoff\nenvelope",
        facecolor=EXPORT,
        weight="bold",
    )
    add_arrow(ax_b, (0.38, 0.40), (0.60, 0.40), label="exchange", label_offset=(0.0, 0.035))
    add_arrow(
        ax_b,
        (0.73, 0.46),
        (0.73, 0.57),
        label="inspect",
        label_offset=(0.05, 0.0),
    )

    future_y = 0.09
    future_boxes = [
        (0.10, "Artifact\nsearch"),
        (0.38, "Permission-\naware sharing"),
        (0.68, "Merge + version\nnegotiation"),
    ]
    for x, text in future_boxes:
        add_box(
            ax_b,
            x,
            future_y,
            0.20,
            0.13,
            text,
            facecolor=FUTURE,
            linestyle=(0, (4, 3)),
            fontsize=8.3,
        )
        add_arrow(
            ax_b,
            (0.73, 0.34),
            (x + 0.10, future_y + 0.13),
            linestyle=(0, (4, 3)),
            linewidth=1.1,
            connectionstyle="arc3,rad=0.10" if x < 0.5 else "arc3,rad=-0.08",
        )

    ax_b.plot([0.10, 0.21], [0.04, 0.04], color=MUTED, linewidth=1.5)
    ax_b.text(0.225, 0.04, "reference implementation", va="center", fontsize=7.8, color=MUTED)
    ax_b.plot([0.58, 0.69], [0.04, 0.04], color=MUTED, linewidth=1.3, linestyle=(0, (4, 3)))
    ax_b.text(0.705, 0.04, "proposed; unevaluated", va="center", fontsize=7.8, color=MUTED)

    fig.subplots_adjust(left=0.025, right=0.985, top=0.985, bottom=0.055, wspace=0.07)
    return fig


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = build_figure()
    for suffix in ("pdf", "svg", "png"):
        kwargs = {"dpi": 300} if suffix == "png" else {}
        metadata = None
        if suffix == "pdf":
            metadata = {"CreationDate": None, "ModDate": None}
        elif suffix == "svg":
            metadata = {"Date": None}
        fig.savefig(
            OUT_DIR / f"figure1.{suffix}",
            bbox_inches="tight",
            facecolor="white",
            metadata=metadata,
            **kwargs,
        )
    plt.close(fig)


if __name__ == "__main__":
    main()
