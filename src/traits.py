"""Trait list for LLM tagging, read from the team Google Sheet (tab TRAITS_TAB).

The sheet is the source of truth. Columns are found by header name (Category, Scale, Trait,
Definition), so inserting a column there doesn't break this. Scale is "Linear" (scored 0-4) or
"Binary" (scored 0/1). Each trait also gets a snake_case `column`, used as its key in the model's
JSON answer and as its column in BigQuery youtube.llm_tagged.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TRAITS_TAB
from sheet import read_rows

HEADERS = ["Category", "Scale", "Trait", "Definition"]


def get_traits():
    """List of {name, column, category, scale ('linear'|'binary'), definition}, in sheet order."""
    rows = read_rows(TRAITS_TAB)
    header = [cell.strip() for cell in rows[0]]
    missing = [name for name in HEADERS if name not in header]
    if missing:
        sys.exit(f"Sheet tab '{TRAITS_TAB}' is missing column(s) {missing}; found {header}.")
    position = {name: header.index(name) for name in HEADERS}

    traits = []
    for row in rows[1:]:
        cells = [cell.strip() for cell in row] + [""] * (len(header) - len(row))
        name = cells[position["Trait"]]
        if not name:
            continue
        scale = cells[position["Scale"]].lower()
        if scale not in ["linear", "binary"]:
            sys.exit(f"Trait '{name}' has Scale '{cells[position['Scale']]}'; expected Linear or Binary.")
        if not cells[position["Definition"]]:
            sys.exit(f"Trait '{name}' has no Definition.")
        traits.append({"name": name, "column": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                       "category": cells[position["Category"]], "scale": scale,
                       "definition": cells[position["Definition"]]})

    columns = [trait["column"] for trait in traits]
    duplicates = [column for index, column in enumerate(columns) if column in columns[:index]]
    if duplicates:
        sys.exit(f"Trait names collide after snake_casing: {duplicates}. Rename them in the sheet.")
    return traits
