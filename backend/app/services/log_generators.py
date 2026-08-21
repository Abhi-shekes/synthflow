"""Realistic-looking single-line log/event text for a STRING field with a
`preset` set (see app.models.field.LogPreset). Every value here is
fabricated by Faker plus random timestamps/IPs/ports — nothing here talks
to a real system, parses real logs, or represents genuine attack traffic.
The security-flavored presets (failed_login, brute_force, sqli_attempt,
ddos_attempt, port_scan, malware_alert) exist to give detection tooling and
dashboards synthetic events to test against, the same defensive use case as
the rest of app.services.error_injection.
"""

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from faker import Faker

faker = Faker()

_LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]
_HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
_HTTP_STATUSES = [200, 201, 204, 301, 302, 400, 401, 403, 404, 500, 502, 503]
_SQLI_PAYLOADS = ["1' OR '1'='1", "'; DROP TABLE users;--", "1 UNION SELECT NULL--", "' OR 1=1 --"]
_MALWARE_SIGNATURES = ["Trojan.GenericKD", "Win32.Emotet", "Ransom.WannaCry", "Backdoor.Cobalt"]


def _recent_timestamp(fmt: str) -> str:
    when = datetime.now(UTC) - timedelta(seconds=random.randint(0, 86_400))
    return when.strftime(fmt)


def _nginx_access_log() -> str:
    return (
        f'{faker.ipv4()} - - [{_recent_timestamp("%d/%b/%Y:%H:%M:%S +0000")}] '
        f'"{random.choice(_HTTP_METHODS)} {faker.uri_path()} HTTP/1.1" '
        f"{random.choice(_HTTP_STATUSES)} {random.randint(200, 50_000)} "
        f'"-" "{faker.user_agent()}"'
    )


def _docker_log() -> str:
    stream = random.choice(["stdout", "stderr"])
    return f'{_recent_timestamp("%Y-%m-%dT%H:%M:%S.%f")}Z {stream} F {faker.sentence(nb_words=6)}'


def _kubernetes_event() -> str:
    kind = random.choice(["Normal", "Warning"])
    reason = random.choice(["Scheduled", "Pulled", "Created", "Started", "Killing", "BackOff"])
    pod = f"{faker.word()}-{faker.hexify('^^^^^^')}"
    return (
        f'{_recent_timestamp("%Y-%m-%dT%H:%M:%SZ")} {kind} {reason} pod/{pod} '
        f"{faker.sentence(nb_words=8)}"
    )


def _linux_syslog() -> str:
    proc = random.choice(["sshd", "sudo", "cron", "systemd", "kernel"])
    return (
        f'{_recent_timestamp("%b %d %H:%M:%S")} {faker.hostname()} '
        f"{proc}[{random.randint(100, 9999)}]: {faker.sentence(nb_words=8)}"
    )


def _application_log() -> str:
    level = random.choice(_LOG_LEVELS)
    component = f"{faker.word().capitalize()}Service"
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} {level} [{component}] '
        f"{faker.sentence(nb_words=10)}"
    )


def _failed_login() -> str:
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} WARN Failed login attempt for user '
        f"'{faker.user_name()}' from {faker.ipv4()} (invalid password)"
    )


def _brute_force() -> str:
    attempts = random.randint(8, 50)
    window = random.randint(10, 120)
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} ALERT {attempts} failed login attempts for '
        f"user '{faker.user_name()}' from {faker.ipv4()} in {window}s — possible brute force"
    )


def _sqli_attempt() -> str:
    return (
        f'{faker.ipv4()} - - [{_recent_timestamp("%d/%b/%Y:%H:%M:%S +0000")}] '
        f'"GET /search?q={random.choice(_SQLI_PAYLOADS)} HTTP/1.1" '
        f"403 {random.randint(200, 2_000)}"
    )


def _ddos_attempt() -> str:
    rps = random.randint(500, 20_000)
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} ALERT Traffic spike from {faker.ipv4()}/24: '
        f"{rps} req/s sustained for {random.randint(5, 300)}s — possible DDoS"
    )


def _port_scan() -> str:
    ports = random.randint(10, 200)
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} ALERT Port scan detected from {faker.ipv4()}: '
        f"{ports} ports probed in {random.randint(1, 30)}s (SYN scan)"
    )


def _malware_alert() -> str:
    return (
        f'{_recent_timestamp("%Y-%m-%d %H:%M:%S")} ALERT Malware signature '
        f'"{random.choice(_MALWARE_SIGNATURES)}" detected on host {faker.hostname()} '
        "— file quarantined"
    )


_LOG_PRESETS: dict[str, Callable[[], str]] = {
    "nginx_access_log": _nginx_access_log,
    "docker_log": _docker_log,
    "kubernetes_event": _kubernetes_event,
    "linux_syslog": _linux_syslog,
    "application_log": _application_log,
    "failed_login": _failed_login,
    "brute_force": _brute_force,
    "sqli_attempt": _sqli_attempt,
    "ddos_attempt": _ddos_attempt,
    "port_scan": _port_scan,
    "malware_alert": _malware_alert,
}


def generate_log_line(preset: str) -> str:
    return _LOG_PRESETS[preset]()
