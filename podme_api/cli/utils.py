"""podme-api cli tool."""

from __future__ import annotations

from dataclasses import fields
import os
from pathlib import Path
from typing import Callable, TypeVar

from rich.box import SIMPLE
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from podme_api.models import BaseDataClassORJSONMixin

T = TypeVar("T", bound=BaseDataClassORJSONMixin)


def pretty_dataclass(  # noqa: C901
    dataclass_obj: T,
    field_formatters: dict[str, Callable[[any, T], any]] | None = None,
    hidden_fields: list[str] | None = None,
    visible_fields: list[str] | None = None,
    title: str | None = None,
    hide_none: bool = True,
    hide_default: bool = True,
) -> Table:
    """Render a dataclass object in a pretty format using rich."""

    field_formatters = field_formatters or {}
    hidden_fields = hidden_fields or []
    visible_fields = visible_fields or []

    table = Table(title=title, show_header=False, title_justify="left")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    if visible_fields:
        # Render fields in the order specified by visible_fields
        for field_name in visible_fields:
            if hidden_fields and field_name in hidden_fields:
                continue

            field = next((f for f in fields(dataclass_obj) if f.name == field_name), None)
            if not field:
                continue

            field_value = getattr(dataclass_obj, field_name)

            if hide_none and field_value is None:
                continue

            if hide_none and isinstance(field_value, list) and len(field_value) == 0:
                continue

            if hide_default and field_value == field.default:
                continue

            if field_name in field_formatters:
                field_value = field_formatters[field_name](field_value, dataclass_obj)
            table.add_row(field_name, str(field_value))
    else:
        # Render all fields (except hidden ones) in the default order
        for field in fields(dataclass_obj):
            if hidden_fields and field.name in hidden_fields:
                continue

            field_value = getattr(dataclass_obj, field.name)

            if hide_none and field_value is None:
                continue

            if hide_none and isinstance(field_value, list) and len(field_value) == 0:
                continue

            if hide_default and field_value == field.default:
                continue

            if field.name in field_formatters:
                field_value = field_formatters[field.name](field_value, dataclass_obj)
            table.add_row(field.name, str(field_value))

    return table


def pretty_dataclass_list(  # noqa: C901
    dataclass_objs: list[T],
    field_formatters: dict[str, Callable[[any, T], any]] | None = None,
    hidden_fields: list[str] | None = None,
    visible_fields: list[str] | None = None,
    field_widths: dict[str, int] | None = None,
    field_order: list[str] | None = None,
    title: str | None = None,
    hide_none: bool = True,
    hide_default: bool = True,
) -> Table | Text:
    """Render a list of dataclass objects in a table format using rich."""

    field_formatters = field_formatters or {}
    hidden_fields = hidden_fields or []
    visible_fields = visible_fields or []
    field_widths = field_widths or {}
    field_order = field_order or []

    if not dataclass_objs:
        if title is not None:
            return Text(f"{title}: No results")
        return Text("No results")

    dataclass_fields = list(fields(dataclass_objs[0]))
    ordered_fields = [f for f in field_order if f in [field.name for field in dataclass_fields]]
    remaining_fields = [f.name for f in dataclass_fields if f.name not in ordered_fields]
    fields_to_render = ordered_fields + remaining_fields

    table = Table(title=title, expand=True)

    for field_name in fields_to_render:
        if hidden_fields and field_name in hidden_fields:
            continue

        if visible_fields and field_name not in visible_fields:
            continue

        table.add_column(
            field_name,
            style="cyan",
            no_wrap=not field_widths.get(field_name, None),
            width=field_widths.get(field_name, None),
        )

    for obj in dataclass_objs:
        row = []
        for field_name in fields_to_render:
            if hidden_fields and field_name in hidden_fields:
                continue

            if visible_fields and field_name not in visible_fields:
                continue

            field = next((f for f in fields(obj) if f.name == field_name), None)
            if not field:
                continue

            field_value = getattr(obj, field_name)

            if hide_none and field_value is None:
                continue

            if hide_default and field_value == field.default:
                continue

            if field_name in field_formatters:
                field_value = field_formatters[field_name](field_value, obj)
            row.append(str(field_value))
        table.add_row(*row)

    return table


def header_panel(title: str, subtitle: str):
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right")
    grid.add_row(
        title,
        subtitle,
    )
    return Panel(
        grid,
        style="white on black",
        box=SIMPLE,
    )


def bold_star(visible: bool = True, suffix=" ", prefix=""):
    return f"{prefix}[bold]*[/bold]{suffix}" if visible else ""


def is_valid_writable_dir(parser, x):
    """Check if directory exists and is writable."""
    if not Path(x).is_dir():
        parser.error(f"{x} is not a valid directory.")
    if not os.access(x, os.W_OK | os.X_OK):
        parser.error(f"{x} is not writable.")
    return Path(x)
