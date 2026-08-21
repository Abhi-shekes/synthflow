"""Bundled starter templates — read-only `ProjectTemplate` JSON files
shipped with the backend (app/starter_templates/*.json, one per roadmap
domain: banking, stock market, smart city, weather, hospital,
manufacturing, CCTV, logistics, GPS fleet, retail, IoT). Each is a plain
file matching the same shape app.services.templates.export_project
produces — there's no separate "starter template" database table or
model, since the whole point of the template format being name-based and
hand-editable is that a starter template is just a template someone
already wrote, not a new kind of object.

A key is the file's stem (`banking.json` -> `"banking"`). Importing one
goes through the exact same `POST /projects/import` route real
export/import already uses — this module only adds discovery
(`list_starter_templates`) and lookup (`load_starter_template`) on top of
that existing mechanism.
"""

import json
from pathlib import Path

from app.schemas.template import ProjectTemplate, StarterTemplateSummary

STARTER_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "starter_templates"


def list_starter_templates() -> list[StarterTemplateSummary]:
    summaries = []
    for path in sorted(STARTER_TEMPLATES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        summaries.append(
            StarterTemplateSummary(
                key=path.stem, name=data["name"], description=data.get("description") or ""
            )
        )
    return summaries


def load_starter_template(key: str) -> ProjectTemplate:
    path = STARTER_TEMPLATES_DIR / f"{key}.json"
    if not path.is_file():
        raise ValueError(f"Unknown starter template '{key}'")
    return ProjectTemplate.model_validate_json(path.read_text())
