"""`synthflow` — the command line.

Two commands:

  init   the modular-installation wizard (below)
  check  run an entity's quality report and exit non-zero if it fails,
         which is what makes the Phase 11 checks usable as a CI gate

`synthflow init` — the modular-installation wizard.

Picks which optional pieces a deployment wants and writes a single `.env`
next to docker-compose.yml. It deliberately does NOT generate a bespoke
compose file: Docker Compose already reads `COMPOSE_PROFILES` from `.env`
and already has profiles for every optional service, so writing that one
variable is enough to make a plain `docker compose up` start exactly what
you selected. Generating a second compose file would be a parallel source
of truth that drifts from docker-compose.yml.

Two variables come out of it:

  COMPOSE_PROFILES  which optional *services* start (redpanda, mosquitto,
                    the monitoring stack)
  SYNTHFLOW_EXTRAS  which optional *Python extras* get installed into the
                    backend image (see pyproject.toml and
                    app.services.install) — this is the half that makes a
                    Kafka-only install genuinely skip aiomqtt rather than
                    just not starting a container

Run it interactively, or non-interactively for scripting/CI:

    synthflow init
    synthflow init --services kafka,monitoring --yes
    synthflow init --all --yes

`synthflow check` — the quality gate.

Generates rows through a running SynthFlow, applies the same checks the
`quality-report` endpoint does, prints what it found and exits 1 if
anything failed. That exit code is the whole point: a report nobody looks
at changes nothing, whereas a red build does.

    synthflow check --project ID --entity ID --token $TOKEN \
        --assert "email.unique" --assert "status.share_paid >= 0.6"

HTTP goes through urllib rather than httpx on purpose — the CLI ships in
the core install, and a gate that drags in a dependency to make one
request is a poor trade.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ENV_FILENAME = ".env"

MANAGED_KEYS = ("COMPOSE_PROFILES", "SYNTHFLOW_EXTRAS")
# Stripped as well as re-written, so re-running the wizard replaces this
# banner instead of stacking another copy of it on every run.
MANAGED_COMMENT = "# Written by `synthflow init`. Re-run it to change these."


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    detail: str
    # Compose profile this turns on, if any.
    profile: str | None
    # Backend extra this installs, if any.
    extra: str | None


OPTIONS: tuple[Option, ...] = (
    Option(
        key="kafka",
        label="Kafka output",
        detail="Adds a Redpanda broker and installs the aiokafka client.",
        profile="kafka",
        extra="kafka",
    ),
    Option(
        key="mqtt",
        label="MQTT output",
        detail="Adds a Mosquitto broker and installs the aiomqtt client.",
        profile="mqtt",
        extra="mqtt",
    ),
    Option(
        key="mysql",
        label="MySQL push",
        detail=(
            "Installs the PyMySQL driver, and adds a MySQL server to push into for trying it out."
        ),
        profile="mysql",
        extra="mysql",
    ),
    Option(
        key="mongo",
        label="MongoDB push",
        detail=(
            "Installs the pymongo driver, and adds a MongoDB server to push into for trying it out."
        ),
        profile="mongo",
        extra="mongo",
    ),
    Option(
        key="parquet",
        label="Parquet and ORC output",
        detail=(
            "Installs pyarrow (~157 MB) so generation jobs can be written "
            "as Parquet or ORC. No extra service."
        ),
        profile=None,
        extra="parquet",
    ),
    Option(
        key="avro",
        label="Avro output",
        detail="Installs fastavro so generation jobs can be written as Avro. No extra service.",
        profile=None,
        extra="avro",
    ),
    Option(
        key="monitoring",
        label="Monitoring dashboard",
        detail="Adds Prometheus, Grafana and Loki. No extra Python deps.",
        profile="monitoring",
        extra=None,
    ),
)

_BY_KEY = {option.key: option for option in OPTIONS}


def _repo_root(start: Path) -> Path:
    """Walk up looking for docker-compose.yml so `synthflow init` works
    from the repo root or from backend/ — the two places someone would
    plausibly run it."""
    for candidate in (start, *start.parents):
        if (candidate / "docker-compose.yml").is_file():
            return candidate
    return start


def _render_env(existing: str, profiles: list[str], extras: list[str]) -> str:
    """Rewrite only the two keys we own, preserving anything else already
    in the file — someone's SECRET_KEY shouldn't vanish because they
    re-ran the wizard."""
    kept = [
        line
        for line in existing.splitlines()
        if not any(line.strip().startswith(f"{key}=") for key in MANAGED_KEYS)
        and line.strip() != MANAGED_COMMENT
    ]
    while kept and not kept[-1].strip():
        kept.pop()

    body = "\n".join(kept)
    if body:
        body += "\n\n"
    return (
        body
        + f"{MANAGED_COMMENT}\n"
        + f"COMPOSE_PROFILES={','.join(profiles)}\n"
        + f"SYNTHFLOW_EXTRAS={','.join(extras)}\n"
    )


def _prompt(options: tuple[Option, ...]) -> list[str]:
    print("Which optional pieces do you want?\n")
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option.label}")
        print(f"     {option.detail}")
    print("\nEnter numbers separated by commas (or press enter for none).")

    raw = input("> ").strip()
    if not raw:
        return []

    chosen: list[str] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if not piece.isdigit() or not (1 <= int(piece) <= len(options)):
            raise SystemExit(f"'{piece}' isn't one of the listed numbers.")
        key = options[int(piece) - 1].key
        if key not in chosen:
            chosen.append(key)
    return chosen


def _parse_services(raw: str) -> list[str]:
    chosen: list[str] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece not in _BY_KEY:
            valid = ", ".join(_BY_KEY)
            raise SystemExit(f"Unknown service '{piece}'. Choose from: {valid}")
        if piece not in chosen:
            chosen.append(piece)
    return chosen


def init(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="synthflow init",
        description="Choose optional services and write .env for docker compose.",
    )
    parser.add_argument(
        "--services",
        default=None,
        help=f"Comma-separated, non-interactive. Options: {', '.join(_BY_KEY)}",
    )
    parser.add_argument("--all", action="store_true", help="Select everything.")
    parser.add_argument("--none", action="store_true", help="Select nothing (core only).")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't ask to confirm.")
    parser.add_argument(
        "--path", default=".", help="Where to write .env (default: nearest repo root)."
    )
    args = parser.parse_args(argv)

    if sum(bool(x) for x in (args.services, args.all, args.none)) > 1:
        raise SystemExit("Pass only one of --services, --all, --none.")

    if args.all:
        chosen = [option.key for option in OPTIONS]
    elif args.none:
        chosen = []
    elif args.services is not None:
        chosen = _parse_services(args.services)
    else:
        chosen = _prompt(OPTIONS)

    profiles = [_BY_KEY[key].profile for key in chosen if _BY_KEY[key].profile]
    extras = [_BY_KEY[key].extra for key in chosen if _BY_KEY[key].extra]

    root = _repo_root(Path(args.path).resolve())
    env_path = root / ENV_FILENAME
    existing = env_path.read_text() if env_path.is_file() else ""
    rendered = _render_env(existing, profiles, extras)

    print()
    if chosen:
        print("Selected: " + ", ".join(_BY_KEY[key].label for key in chosen))
    else:
        print("Selected: core only (no optional services)")
    print(f"Writing {env_path}:\n")
    for line in rendered.splitlines():
        if any(line.startswith(f"{key}=") for key in MANAGED_KEYS):
            print(f"    {line}")

    if not args.yes:
        answer = input("\nWrite it? [Y/n] ").strip().lower()
        if answer not in ("", "y", "yes"):
            print("Nothing written.")
            return 1

    env_path.write_text(rendered)

    print("\nDone. Next:\n")
    if extras:
        print("    docker compose build backend   # picks up SYNTHFLOW_EXTRAS")
    print("    docker compose up -d")
    print("    docker compose exec backend alembic upgrade head")
    if "monitoring" in chosen:
        print("\n  Grafana: http://localhost:3001")
    print("  SynthFlow: http://localhost:3000")
    return 0


def check(argv: list[str] | None = None) -> int:
    """Run an entity's quality report and return a process exit code."""
    parser = argparse.ArgumentParser(
        prog="synthflow check",
        description="Generate rows, check them, and exit non-zero if the checks fail.",
    )
    parser.add_argument("--url", default="http://localhost:8001", help="SynthFlow base URL")
    parser.add_argument("--token", required=True, help="access token")
    parser.add_argument("--project", required=True, help="project id")
    parser.add_argument("--entity", required=True, help="entity id")
    parser.add_argument("--count", type=int, default=1000, help="rows to generate")
    parser.add_argument(
        "--assert",
        dest="assertions",
        action="append",
        default=[],
        metavar="EXPR",
        help="a boolean expression that must hold; repeatable",
    )
    parser.add_argument("--json", action="store_true", help="print the raw report instead")
    args = parser.parse_args(argv)

    endpoint = (
        f"{args.url.rstrip('/')}/api/v1/projects/{args.project}"
        f"/entities/{args.entity}/quality-report"
    )
    body = json.dumps({"count": args.count, "assertions": args.assertions}).encode()
    request = urllib.request.Request(endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {args.token}")

    try:
        with urllib.request.urlopen(request) as response:
            report = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"quality report failed: HTTP {exc.code} {detail}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"could not reach {args.url}: {exc.reason}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["passes"] else 1

    print(f"{report['rows']} rows generated")

    for finding in report["diagnostics"]["findings"]:
        print(f"  ! {finding}")

    for violation in report["observation"]["violations"]:
        print(f"  VIOLATION {violation['field']}: {violation['detail']}")

    for result in report["assertions"]:
        if result["error"]:
            print(f"  ERROR  {result['expression']}  <- {result['error']}")
        else:
            print(f"  {'PASS' if result['passed'] else 'FAIL'}   {result['expression']}")

    if report["passes"]:
        print("PASS")
        return 0
    print("FAIL")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "init":
        return init(argv[1:])
    if argv and argv[0] == "check":
        return check(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    print("usage: synthflow init [--services ...] [--all] [--none] [--yes]")
    print("       synthflow check --project ID --entity ID --token TOKEN [--assert EXPR]")
    return 1 if argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
