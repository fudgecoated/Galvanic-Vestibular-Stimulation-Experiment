# trial_randomizer.py
# Run with:
# python trial_randomizer.py
#
# Requires:
# pip install reportlab

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path


# ==============================
# EXPERIMENT CONFIG
# ==============================

CONTROL_LABEL = "Control"

CONDITIONS = [
    "No-Vision // GVS // Weight A",
    "No-Vision // GVS // Weight B",
    "No-Vision // GVS // No-Weight",
    "Vision // GVS // Weight A",
    "Vision // GVS // No-Weight",
    "No-Vision // No-GVS // No-Weight",
    "Vision // No-GVS // Weight A",
]

SEED = None  # Optional reproducibility


# ==============================
# PATH SETUP
# ==============================

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "results" / "trial_orders"

SCRIPT_NAME = Path(__file__).name


# ==============================
# TRIAL GENERATION
# ==============================

def build_block_trials():
    """Each condition appears once per block."""
    trials = CONDITIONS.copy()
    random.shuffle(trials)
    return trials


def add_controls(trials):
    """Insert control before, between, and after trials."""
    out = [CONTROL_LABEL]

    for t in trials:
        out.append(t)
        out.append(CONTROL_LABEL)

    return out


# ==============================
# TEXT WRAPPING
# ==============================

def draw_wrapped_line(c, text, x, y, max_width,
                      font_name="Helvetica", font_size=11, leading=14):

    c.setFont(font_name, font_size)

    words = text.split(" ")
    line = ""

    for w in words:
        test = (line + " " + w).strip()

        if c.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            c.drawString(x, y, line)
            y -= leading
            line = w

    if line:
        c.drawString(x, y, line)
        y -= leading

    return y


# ==============================
# WRITE BLOCK CONTENT
# ==============================

def write_block(c, title, items, page_width, page_height):

    left = 60
    right = 60

    # FIXED: start lower so header never overlaps
    top = 160

    bottom = 60

    max_width = page_width - left - right

    y = page_height - top

    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, y, title)

    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Total items (including controls): {len(items)}")

    y -= 20

    for i, item in enumerate(items, start=1):

        text = f"{i:02d}. {item}"

        if y < bottom + 20:
            c.showPage()
            y = page_height - 80

        y = draw_wrapped_line(c, text, left, y, max_width)


# ==============================
# MAIN SCRIPT
# ==============================

def main():

    if SEED is not None:
        random.seed(SEED)

    # Create two randomized blocks
    block_A_trials = build_block_trials()
    block_B_trials = build_block_trials()

    block_A = add_controls(block_A_trials)
    block_B = add_controls(block_B_trials)

    blocks = [
        ("Block A", block_A),
        ("Block B", block_B)
    ]

    # Randomize block order
    random.shuffle(blocks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()

    date_title = now.strftime("%b %d, %Y") + " Experimental Order"
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    filename = now.strftime("%Y%m%d_%H%M") + "_experimental_order.pdf"

    output_path = OUTPUT_DIR / filename

    # Import reportlab
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        raise SystemExit(
            "reportlab not installed\n"
            "Install with: pip install reportlab"
        )

    page_width, page_height = letter

    c = canvas.Canvas(str(output_path), pagesize=letter)

    # ==============================
    # HEADER
    # ==============================

    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, page_height - 50, date_title)

    c.setFont("Helvetica", 10)
    c.drawString(60, page_height - 70, f"Document generated: {timestamp}")

    note = (
        f"Note: Experimental order randomized automatically using "
        f"{SCRIPT_NAME} within the GVS analysis repository."
    )

    draw_wrapped_line(
        c,
        note,
        60,
        page_height - 90,
        page_width - 120,
        font_name="Helvetica-Oblique",
        font_size=9,
        leading=12
    )

    block_order_text = f"Randomized block order: 1) {blocks[0][0]}   2) {blocks[1][0]}"

    c.setFont("Helvetica", 10)
    c.drawString(60, page_height - 115, block_order_text)

    # ==============================
    # BLOCK 1
    # ==============================

    write_block(
        c,
        f"Block 1 ({blocks[0][0]})",
        blocks[0][1],
        page_width,
        page_height
    )

    # ==============================
    # BLOCK 2
    # ==============================

    c.showPage()

    write_block(
        c,
        f"Block 2 ({blocks[1][0]})",
        blocks[1][1],
        page_width,
        page_height
    )

    c.save()

    print("Saved:", output_path)
    print("Block 1:", blocks[0][0])
    print("Block 2:", blocks[1][0])


if __name__ == "__main__":
    main()
