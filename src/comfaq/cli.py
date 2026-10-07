from pathlib import Path

import typer

from comfaq.import_gsheet import import_entries
from comfaq.pdf import build_pdf

app = typer.Typer()


@app.command("import-gsheet")
def import_gsheet_command() -> None:
    import_entries()


@app.command()
def pdf(output: Path) -> None:
    build_pdf(output)
