"""Operational commands. Run with `python -m app.cli <command>`."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_scope
from app.importers.excel.commit import run_import
from app.importers.excel.preview import ImportPreview
from app.models import Program, User
from app.schemas.imports import ImportOverrides
from app.services.errors import DomainError

cli = typer.Typer(help="Joint CMC tracker maintenance commands", no_args_is_help=True)


@cli.callback()
def _main() -> None:
    """Force multi-command (group) mode so subcommand names are always required."""


def _program(db: Session) -> Program:
    program = db.scalar(select(Program).where(Program.code == get_settings().program_code))
    if program is None:
        raise typer.BadParameter("Program not initialised; run `bootstrap` first")
    return program


def _actor(db: Session, email: str | None) -> User:
    stmt = select(User).where(User.is_active.is_(True))
    if email:
        stmt = stmt.where(User.email == email.strip().lower())
    else:
        stmt = stmt.where(User.role == "admin").order_by(User.id)
    user = db.scalar(stmt)
    if user is None:
        raise typer.BadParameter("No matching active user; create an admin first")
    return user


def _print_preview(preview: ImportPreview) -> None:
    actions = sum(1 for row in preview.rows if row.kind == "action")
    typer.echo(
        f"{len(preview.rows)} rows: {actions} actions, {len(preview.rows) - actions} notes, "
        f"{preview.update_count} updates"
    )
    for row in preview.rows:
        for message in row.warnings:
            typer.echo(f"  warning row {row.excel_row} (entry {row.entry_no}): {message}")
    for field_name, values in preview.unmapped.items():
        typer.echo(f"  unmapped {field_name}: {', '.join(values)}")
    for error in preview.errors:
        typer.echo(f"  error: {error}")


@cli.command("import-excel")
def import_excel(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    actor: Annotated[
        str | None, typer.Option(help="Acting user's email; defaults to the first active admin")
    ] = None,
    overrides: Annotated[
        str, typer.Option(help='JSON, e.g. {"owner": {"formulation": "gensci"}}')
    ] = "{}",
    commit: Annotated[bool, typer.Option("--commit", help="Write to the database")] = False,
) -> None:
    """Preview (default) or import the Master Track Sheet."""
    parsed = ImportOverrides.model_validate_json(overrides)
    with session_scope() as db:
        program = _program(db)
        acting = _actor(db, actor)
        try:
            preview, result = run_import(
                db,
                actor=acting,
                program=program,
                source=path,
                file_name=path.name,
                overrides=parsed,
                import_date=date.today(),
                commit=commit,
            )
        except DomainError as exc:
            typer.echo(f"error: {exc.message} {json.dumps(exc.fields or {})}")
            raise typer.Exit(code=1) from exc
    _print_preview(preview)
    if result is None:
        if preview.committable:
            typer.echo("dry run; pass --commit to write")
            return
        typer.echo("not committable; resolve the problems above (use --overrides)")
        raise typer.Exit(code=1)
    typer.echo(
        f"imported {result.items_created} items and {result.updates_created} updates "
        f"(audit event {result.audit_event_id})"
    )


if __name__ == "__main__":
    cli()
