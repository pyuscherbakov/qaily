# /// script
# requires-python = ">=3.10"
# dependencies = ["keyring==25.6.0"]
# ///
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

import keyring

SERVICE = "qaily"


class MissingSecret(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"qaily: не найден токен {name}. Задайте: uvx keyring set {SERVICE} {name} "
            f"(или переменную {env_name(name)})"
        )


def env_name(name: str) -> str:
    return f"QAILY_{name.upper()}"


def resolve_secret(name: str) -> tuple[str | None, str]:
    value = os.environ.get(env_name(name), "").strip()
    if value:
        return value, "env"
    try:
        value = (keyring.get_password(SERVICE, name) or "").strip()
    except Exception:
        value = ""
    return (value, "keyring") if value else (None, "missing")


def require_secret(name: str) -> str:
    value, _ = resolve_secret(name)
    if value is None:
        raise MissingSecret(name)
    return value


def build_env(secrets: list[str], dirs: list[str], base: Mapping[str, str]) -> dict[str, str]:
    env = dict(base)
    for spec in secrets:
        var, name = spec.split("=", 1)
        if name.endswith("?"):
            value, _ = resolve_secret(name[:-1])
            if value is not None:
                env[var] = value
        else:
            env[var] = require_secret(name)
    for spec in dirs:
        var, raw_path = spec.split("=", 1)
        path = Path(raw_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        env[var] = str(path)
    return env


def render_headers(specs: list[str]) -> dict[str, str]:
    headers = {}
    for spec in specs:
        header, template = spec.split("=", 1)
        headers[header] = re.sub(r"\{(\w+)\}", lambda m: require_secret(m.group(1)), template)
    return headers


CHECKS = {
    "allure": ("https://astbroker.qatools.cloud/api/rs/project", "Authorization", "Api-Token {}"),
    "redmine": ("https://redmine.fast-system.ru/users/current.json", "X-Redmine-API-Key", "{}"),
    "kaiten": ("https://lab-company.kaiten.ru/api/latest/users/current", "Authorization", "Bearer {}"),
    "context7": None,
}


def probe(url: str, header: str, value: str) -> tuple[str, bool]:
    request = urllib.request.Request(url, headers={header: value})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return f"HTTP {response.status}", True
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}", False
    except Exception as error:
        return f"сеть: {type(error).__name__}", False


def check() -> int:
    healthy = True
    for name, endpoint in CHECKS.items():
        value, source = resolve_secret(name)
        if value is None:
            if endpoint is None:
                print(f"{name}: не найден (необязательный)")
            else:
                print(f"{name}: не найден — {MissingSecret(name)}")
                healthy = False
            continue
        if endpoint is None:
            print(f"{name}: {source}")
            continue
        url, header, template = endpoint
        result, ok = probe(url, header, template.format(value))
        print(f"{name}: {source} — {result}")
        healthy = healthy and ok
    return 0 if healthy else 1


def launch(cmd: list[str], env: dict[str, str]) -> int:
    executable = shutil.which(cmd[0], path=env.get("PATH"))
    if executable is None:
        print(f"qaily: команда не найдена: {cmd[0]}", file=sys.stderr)
        return 127
    args = [executable, *cmd[1:]]
    if sys.platform == "win32":
        return subprocess.run(args, env=env).returncode
    os.execvpe(executable, args, env)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    command = []
    if "--" in argv:
        split_at = argv.index("--")
        argv, command = argv[:split_at], argv[split_at + 1 :]

    parser = argparse.ArgumentParser(prog="qaily_launch.py")
    modes = parser.add_subparsers(dest="mode", required=True)
    run_mode = modes.add_parser("run")
    run_mode.add_argument("--secret", action="append", default=[])
    run_mode.add_argument("--dir", action="append", default=[])
    headers_mode = modes.add_parser("headers")
    headers_mode.add_argument("specs", nargs="+")
    modes.add_parser("check")
    args = parser.parse_args(argv)

    if args.mode == "check":
        return check()
    try:
        if args.mode == "headers":
            print(json.dumps(render_headers(args.specs)))
            return 0
        if not command:
            parser.error("run: после -- нужна команда сервера")
        return launch(command, build_env(args.secret, args.dir, os.environ))
    except MissingSecret as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
