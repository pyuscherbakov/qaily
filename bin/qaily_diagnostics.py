"""Read-only diagnostics; never expose secret values or endpoint details."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
from urllib.parse import urlsplit

from qaily_launch import CHECKS, MissingSecret, probe, resolve_secret


@dataclass(frozen=True)
class CheckResult:
    name: str
    layer: str
    status: str
    detail: str


def token_checks(settings: Mapping[str, str], *, skip_allure: bool = False) -> list[CheckResult]:
    paths = {'allure': ('testops_url', '/api/rs/project'),
             'redmine': ('redmine_url', '/users/current.json'),
             'kaiten': ('kaiten_url', '/api/latest/users/current')}
    results = []
    for name, endpoint in CHECKS.items():
        if skip_allure and name == 'allure':
            continue
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
    servers = data.get('mcp_servers', {})
    if not isinstance(servers, dict):
        return [CheckResult('applied config', 'config', 'error', 'неверная конфигурация серверов')]
    server = servers.get('qaily_testops', {})
    if not isinstance(server, dict):
        return [CheckResult('applied config', 'config', 'error', 'неверная конфигурация сервера')]
    helper = server.get('http_headers_helper')
    if isinstance(helper, str):
        try:
            # list2cmdline emits Windows paths with literal backslashes; POSIX
            # shlex would consume them, even when the path has no spaces.
            windows = bool(re.search(r'(?:[A-Za-z]:\\|\\\\)', helper))
            args = shlex.split(helper, posix=not windows)
            script = args[args.index('--script') + 1]
            if windows and len(script) >= 2 and script[0] == script[-1] == '"':
                script = script[1:-1]
            exists = Path(script).is_file()
        except (ValueError, IndexError, OSError):
            exists = False
        return [CheckResult('helper path', 'config', 'ok' if exists else 'error',
                            'файл helper найден' if exists else 'путь helper устарел или не распознан')]
    return [CheckResult('applied config', 'config', 'ok' if server else 'not_checked',
                        'top-level сервер настроен' if server else 'top-level сервер отсутствует')]


def format_checks(results: Sequence[CheckResult]) -> str:
    return '\n'.join(f'{result.name}: {result.detail}' for result in results)


def codex_testops_check(settings: Mapping[str, str], path: Path,
                        process_env: Mapping[str, str] | None) -> CheckResult:
    """Conservative inspection; process_env is supplied only when known to match Codex."""
    def result(status: str, detail: str) -> CheckResult:
        return CheckResult('Codex TestOps', 'http', status, detail)

    try:
        import tomllib
    except ImportError:
        return result('not_checked', 'TOML parser недоступен')
    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
        servers = data.get('mcp_servers', {})
        plugins = data.get('plugins', {})
        plugin = plugins.get('qaily@qaily-codex', {})
        bundled = plugin.get('mcp_servers', {}).get('testops', {})
        top = servers.get('qaily_testops', {})
        if not all(isinstance(x, dict) for x in (servers, plugins, plugin, bundled, top)):
            raise ValueError
        if any('enabled' in item and not isinstance(item['enabled'], bool) for item in (top, bundled)):
            raise ValueError
        top_enabled = bool(top) and top.get('enabled', True) is not False
        bundled_enabled = bundled.get('enabled', True) is not False
    except FileNotFoundError:
        return result('not_checked', 'применённая конфигурация недоступна')
    except (OSError, UnicodeError, ValueError, AttributeError, TypeError):
        return result('error', 'не удалось прочитать конфигурацию')
    if top_enabled and bundled_enabled:
        return result('error', 'возможны два активных подключения TestOps')
    if not top_enabled:
        if bundled_enabled:
            return result('not_checked', 'bundled TestOps: активный URL и авторизация требуют проверки в клиенте')
        return result('not_checked', 'активное подключение TestOps не определено')
    expected = settings['testops_url'].rstrip('/') + '/api/mcp'
    if top.get('url') != expected:
        return result('not_checked', 'URL применённого подключения отличается от settings или неизвестен')
    # Other top-level registrations can have their own credentials and policy.
    # Unknown transports or ambiguous URLs cannot establish uniqueness safely.
    def endpoint_key(value: object) -> tuple[str, str, int, str] | None:
        if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
            return None
        try:
            url = urlsplit(value)
            if (url.scheme not in ('http', 'https') or not url.hostname or url.username is not None
                    or url.password is not None or url.query or url.fragment or url.port == 0
                    or '%' in url.path or '\\' in value or any(part in ('.', '..') for part in url.path.split('/'))):
                return None
            return (url.scheme, url.hostname.lower(), url.port or (443 if url.scheme == 'https' else 80),
                    url.path.rstrip('/'))
        except ValueError:
            return None

    expected_key = endpoint_key(expected)
    if expected_key is None:
        return result('not_checked', 'не удалось сравнить адрес подключения')
    for identity, other in servers.items():
        if identity == 'qaily_testops':
            continue
        if not isinstance(other, dict) or not isinstance(other.get('enabled', True), bool):
            return result('not_checked', 'не удалось проверить другие подключения')
        if other.get('enabled', True) is False:
            continue
        other_key = endpoint_key(other.get('url'))
        if other_key is None or 'command' in other:
            return result('not_checked', 'не удалось проверить другие подключения')
        if other_key == expected_key:
            return result('error', 'возможны два активных подключения TestOps')
    if any(key in top for key in ('bearer_token_env_var', 'http_headers')):
        return result('not_checked', 'дополнительная авторизация не распознана')
    headers = top.get('env_http_headers', {})
    helper = top.get('http_headers_helper')
    if headers == {'Authorization': 'QAILY_TESTOPS_AUTHORIZATION'} and helper is None:
        mode = 'env-header'
    elif not headers and isinstance(helper, str):
        try:
            windows = bool(re.search(r'(?:[A-Za-z]:\\|\\\\)', helper))
            args = shlex.split(helper, posix=not windows)
            if windows:
                args = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] == '"' else a for a in args]
            valid = (len(args) == 7 and args[:4] == ['uv', 'run', '-q', '--script']
                     and Path(args[4]).resolve() == Path(__file__).resolve().parent / 'qaily_launch.py'
                     and args[5:] == ['headers', 'Authorization=Api-Token {allure}'])
        except (ValueError, OSError):
            valid = False
        if not valid:
            return result('not_checked', 'helper не распознан')
        mode = 'keyring-helper'
    else:
        return result('not_checked', 'режим авторизации не распознан')
    if process_env is None:
        return result('not_checked', f'{mode}: окружение процесса Codex неизвестно')
    if mode == 'env-header':
        value = process_env.get('QAILY_TESTOPS_AUTHORIZATION', '').strip()
    else:
        try:
            value, _ = resolve_secret('allure')
        except Exception:
            value = None
        value = f'Api-Token {value}' if value else ''
    if not value:
        return result('error', f'{mode}: авторизация отсутствует')
    try:
        message, ok = probe(settings['testops_url'].rstrip('/') + '/api/rs/project', 'Authorization', value, follow_redirects=False)
        if not re.fullmatch(r'HTTP \d{3}', message):
            message, ok = 'сетевая ошибка или ошибка проверки', False
    except Exception:
        message, ok = 'ошибка проверки', False
    return result('ok' if ok else 'error', f'{mode}: {message}; HTTP не подтверждает MCP')
