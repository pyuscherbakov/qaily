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


def format_helper_command(script: str, *, windows: bool) -> str:
    args = ['uv', 'run', '-q', '--script', script, 'headers', 'Authorization=Api-Token {allure}']
    return subprocess.list2cmdline(args) if windows else shlex.join(args)


def render_codex_fragment(package_root: Path, settings: Mapping[str, str]) -> str:
    script = package_root.resolve() / 'bin' / 'qaily_launch.py'
    if not script.is_file():
        raise ValueError('qaily: qaily_launch.py не найден; укажите актуальный installedPath установленного пакета')
    helper = format_helper_command(str(script), windows=os.name == 'nt')
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    return ('[plugins."qaily@qaily-codex".mcp_servers.testops]\n'
            'enabled = false\n\n'
            '[mcp_servers.qaily_testops]\n'
            f'url = {quote(settings["testops_url"].rstrip("/") + "/api/mcp")}\n'
            f'http_headers_helper = {quote(helper)}\n'
            'default_tools_approval_mode = "prompt"\n')


def render_policy(catalog: Mapping[str, list[str]], approved_reads: Mapping[str, list[str]],
                  server_ids: Mapping[str, str], *,
                  connection_kinds: Mapping[str, str] | None = None) -> str:
    """Render policies for exactly observed and independently approved tools."""
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    sections = []
    for service in ('testops', 'kaiten', 'context7', 'jam'):
        if service not in server_ids:
            continue
        identity = server_ids[service]
        known = {'testops': {'testops': 'bundled', 'qaily_testops': 'top-level'},
                 'kaiten': {'kaiten': 'bundled'}, 'context7': {'context7': 'bundled'},
                 'jam': {'jam': 'bundled'}}
        kind = (connection_kinds or {}).get(service) or known[service].get(identity)
        if kind not in ('bundled', 'top-level'):
            raise ValueError(f'qaily: specify connection kind for {service} ({identity})')
        server_id = quote(identity)
        base = (f'mcp_servers.{server_id}' if kind == 'top-level' else
                f'plugins."qaily@qaily-codex".mcp_servers.{server_id}')
        observed = set(catalog.get(service, []))
        reads = sorted(observed.intersection(approved_reads.get(service, [])))
        if service == 'testops':
            sections.append(f'[{base}]\ndefault_tools_approval_mode = "prompt"')
            for tool in reads:
                sections.append(f'[{base}.tools.{quote(tool)}]\napproval_mode = "approve"')
        else:
            sections.append(f'[{base}]\nenabled_tools = {json.dumps(reads, ensure_ascii=False)}')
    return '\n\n'.join(sections) + ('\n' if sections else '')


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    render = sub.add_parser('render')
    render.add_argument('--package-root', type=Path, required=True)
    render.add_argument('--settings', type=Path)
    policy = sub.add_parser('policy')
    policy.add_argument('--catalog', type=Path, required=True)
    policy.add_argument('--testops-connection', choices=('bundled', 'top-level'), default='bundled')
    policy.add_argument('--approved-reads', type=Path, default=Path(__file__).resolve().parents[1] / 'references/policies/read-tools.json')
    args = parser.parse_args()
    try:
        if args.mode == 'policy':
            catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
            approved = json.loads(args.approved_reads.read_text(encoding='utf-8'))
            print(render_policy(catalog, approved, {'testops': 'testops' if args.testops_connection == 'bundled' else 'qaily_testops', 'kaiten': 'kaiten', 'context7': 'context7', 'jam': 'jam'}), end='')
        else:
            print(render_codex_fragment(args.package_root, load_settings(args.settings)), end='')
        return 0
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
