from pathlib import Path
from typing import Annotated

import typer

from comfaq.changelog import build_changelog
from comfaq.csv_export import build_csv
from comfaq.import_gsheet import import_entries
from comfaq.pdf import build_pdf

app = typer.Typer()


@app.command("import-gsheet")
def import_gsheet_command() -> None:
    import_entries()


@app.command()
def pdf(output: Path) -> None:
    build_pdf(output)


@app.command("csv")
def csv_command(output: Path) -> None:
    build_csv(output)


@app.command()
def changelog(output: Path, limit: Annotated[int, typer.Option()]) -> None:
    build_changelog(output, limit)
