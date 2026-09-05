#!/usr/bin/env python3
"""Embed the marimo grid layout into the notebook as a data URI.

molab mirrors a single .py file and nothing around it, so a `layout_file` naming
`layouts/marimo_app.grid.json` resolves to nothing there: marimo logs "Layout
file ... does not exist", falls back to the vertical view, and the grid view
comes up empty because no cell has a position. Inlining the layout as a data URI
makes it travel with the file. marimo decodes it in
`marimo/_runtime/layout/layout.py:63`.

`apps/layouts/marimo_app.grid.json` stays the editable source -- marimo writes it
when you rearrange cells in the editor. Re-run this afterwards:

    pixi run layout
"""

import base64
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "apps" / "marimo_app.py"
LAYOUT = REPO / "apps" / "layouts" / "marimo_app.grid.json"

# layout_file="..." on its own line inside the marimo.App(...) call.
LAYOUT_LINE = re.compile(r'^(?P<indent>\s*)layout_file\s*=\s*(?P<value>"[^"]*"|\'[^\']*\'),\s*$',
                         re.MULTILINE)


def main() -> None:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    cells = layout["data"]["cells"]

    source = NOTEBOOK.read_text(encoding="utf-8")
    declared = source.count("@app.cell")
    if len(cells) != declared:
        raise SystemExit(
            f"{LAYOUT.name} has {len(cells)} entries but the notebook declares "
            f"{declared} cells. marimo matches them by position, so a mismatch "
            f"silently misplaces every cell after the gap."
        )

    uri = "data:application/json;base64," + base64.b64encode(
        json.dumps(layout, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    match = LAYOUT_LINE.search(source)
    if not match:
        raise SystemExit(f"no layout_file= line found in {NOTEBOOK}")
    if match.group("value").strip('"\'') == uri:
        print(f"already current ({len(cells)} cells, {len(uri)} chars)")
        return

    updated = source[:match.start()] + f'{match.group("indent")}layout_file="{uri}",\n' + source[match.end():]
    NOTEBOOK.write_text(updated, encoding="utf-8")
    print(f"embedded {len(cells)} cell positions into {NOTEBOOK.name} ({len(uri)} chars)")


if __name__ == "__main__":
    sys.exit(main())
