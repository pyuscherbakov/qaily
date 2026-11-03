"""Render a non-secret Codex configuration fragment; never edit user files."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from collections.abc import Mapping

from qaily_config import load_settings


def render_codex_fragment(package_root: Path, settings: Mapping[str, str]) -> str:
    script = str(package_root.resolve() / 'bin' / 'qaily_launch.py')
    args = ['uv', 'run', '-q', '--script', script, 'headers', 'Authorization=Api-Token {allure}']
    helper = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    return ('[plugins."qaily@qaily-codex".mcp_servers.testops]\n'
            'enabled = false\n\n'
            '[mcp_servers.qaily_testops]\n'
            f'url = {quote(settings["testops_url"].rstrip("/") + "/api/mcp")}\n'
            f'http_headers_helper = {quote(helper)}\n'
            'default_tools_approval_mode = "prompt"\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    render = sub.add_parser('render')
    render.add_argument('--package-root', type=Path, required=True)
    render.add_argument('--settings', type=Path)
    args = parser.parse_args()
    try:
        print(render_codex_fragment(args.package_root, load_settings(args.settings)), end='')
        return 0
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
