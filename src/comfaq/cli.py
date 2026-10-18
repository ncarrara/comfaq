from pathlib import Path
from typing import Annotated

import typer

from comfaq.changelog import build_changelog, build_history
from comfaq.csv_export import build_csv
from comfaq.discord import send_discord
from comfaq.import_gsheet import import_entries
from comfaq.import_gw_faq import import_gw_faq
from comfaq.pdf import build_pdf

app = typer.Typer()


@app.command("import-gsheet")
def import_gsheet_command() -> None:
    import_entries()


@app.command("import-gw-faq")
def import_gw_faq_command() -> None:
    import_gw_faq()


@app.command()
def pdf(output: Path, branch: Annotated[str, typer.Option()]) -> None:
    build_pdf(output, branch)


@app.command("csv")
def csv_command(output: Path) -> None:
    build_csv(output)


@app.command()
def changelog(output: Path, limit: Annotated[int, typer.Option()]) -> None:
    build_changelog(output, limit)


@app.command()
def history(output: Path) -> None:
    build_history(output)


@app.command()
def discord(
    bot_token: Annotated[str, typer.Option(envvar="DISCORD_BOT_TOKEN")],
    before: Annotated[str, typer.Option()],
    after: Annotated[str, typer.Option()],
    branch: Annotated[str, typer.Option()],
    sheet: Annotated[str, typer.Option()],
    repo: Annotated[str, typer.Option()],
    site_url: Annotated[str, typer.Option()],
) -> None:
    send_discord(bot_token, before, after, branch, sheet, repo, site_url)
