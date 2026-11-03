"""Read-only diagnostics; never expose secret values or endpoint details."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import shlex

from qaily_launch import CHECKS, MissingSecret, probe, resolve_secret


@dataclass(frozen=True)
class CheckResult:
    name: str
    layer: str
    status: str
    detail: str


def token_checks(settings: Mapping[str, str]) -> list[CheckResult]:
    paths = {'allure': ('testops_url', '/api/rs/project'),
             'redmine': ('redmine_url', '/users/current.json'),
             'kaiten': ('kaiten_url', '/api/latest/users/current')}
    results = []
    for name, endpoint in CHECKS.items():
        try:
            value, source = resolve_secret(name)
        except Exception:
            value, source = None, 'missing'
        if not value:
            detail = 'не найден (необязательный)' if endpoint is None else f'не найден — {MissingSecret(name)}'
            results.append(CheckResult(name, 'secret', 'ok' if endpoint is None else 'error', detail))
            continue
        source = source if source in ('env', 'keyring') else 'unknown'
        if endpoint is None:
            results.append(CheckResult(name, 'secret', 'ok', source))
            continue
        key, path = paths[name]
        _, header, template = endpoint
        try:
            message, ok = probe(settings[key] + path, header, template.format(value))
            # Only an allowlisted status or exception type can enter output.
            match = re.fullmatch(r'HTTP (\d{3})', message)
            network = re.fullmatch(r'сеть: ([A-Za-z][A-Za-z0-9_]{0,63})', message)
            if match:
                message = 'HTTP ' + match.group(1)
            elif network and network.group(1) in {'URLError', 'TimeoutError', 'OSError', 'ConnectionError', 'ConnectionResetError', 'ConnectionRefusedError'}:
                message = 'сеть: ' + network.group(1)
            else:
                message, ok = 'ошибка проверки', False
        except Exception:
            message, ok = 'ошибка проверки', False
        detail = f'{source} — {message}'
        if message == 'HTTP 403':
            detail += ' (возможен недостаток прав)'
        results.append(CheckResult(name, 'http', 'ok' if ok else 'error', detail))
    results.append(CheckResult('mcp', 'mcp', 'not_checked', 'HTTP не проверяет initialize или каталог MCP'))
    return results


def static_policy_check(configured: bool) -> CheckResult:
    detail = 'статическая конфигурация есть; применение не проверено' if configured else 'применение не проверено'
    return CheckResult('runtime policy', 'policy', 'not_checked', detail)


def applied_config_check(path: Path) -> list[CheckResult]:
    """Inspect an applied top-level config without reporting contents or paths."""
    try:
        import tomllib
    except ImportError:
        return [CheckResult('applied config', 'config', 'not_checked', 'TOML parser недоступен')]
    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return [CheckResult('applied config', 'config', 'not_checked', 'файл отсутствует')]
    except (OSError, UnicodeError, ValueError):
        return [CheckResult('applied config', 'config', 'error', 'не удалось прочитать TOML')]
    server = data.get('mcp_servers', {}).get('qaily_testops', {})
    if not isinstance(server, dict):
        return [CheckResult('applied config', 'config', 'error', 'неверная конфигурация сервера')]
    helper = server.get('http_headers_helper')
    if isinstance(helper, str):
        try:
            args = shlex.split(helper, posix=True)
            script = args[args.index('--script') + 1]
            exists = Path(script).is_file()
        except (ValueError, IndexError, OSError):
            exists = False
        return [CheckResult('helper path', 'config', 'ok' if exists else 'error',
                            'файл helper найден' if exists else 'путь helper устарел или не распознан')]
    return [CheckResult('applied config', 'config', 'ok' if server else 'not_checked',
                        'top-level сервер настроен' if server else 'top-level сервер отсутствует')]


def format_checks(results: Sequence[CheckResult]) -> str:
    return '\n'.join(f'{result.name}: {result.detail}' for result in results)
