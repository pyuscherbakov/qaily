"""Non-secret service configuration shared by Qaily clients."""
import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

DEFAULTS = {
    'testops_url': 'https://astbroker.qatools.cloud',
    'redmine_url': 'https://redmine.fast-system.ru',
    'kaiten_url': 'https://lab-company.kaiten.ru',
}


def load_settings(path: Path | None = None) -> dict[str, str]:
    path = path if path is not None else Path.home() / '.qaily' / 'config.json'
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return DEFAULTS.copy()
    except (OSError, UnicodeError):
        raise ValueError('qaily config: не удалось прочитать файл настроек UTF-8') from None
    try:
        values = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('qaily config: исправьте JSON в файле настроек') from None
    if not isinstance(values, dict) or set(values) - DEFAULTS.keys():
        raise ValueError('qaily config: разрешены только testops_url, redmine_url, kaiten_url')
    result = DEFAULTS.copy()
    for key, value in values.items():
        try:
            parsed = urlsplit(value) if isinstance(value, str) else None
            valid = (parsed and parsed.scheme in ('http', 'https') and parsed.hostname
                     and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment and parsed.port != 0
                     and not any(c.isspace() or ord(c) < 32 for c in value))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f'qaily config: {key} должен быть HTTP(S) base URL без учётных данных, query и fragment')
        result[key] = value.rstrip('/')
    return result


def service_env(service: str, settings: Mapping[str, str]) -> dict[str, str]:
    if service == 'redmine':
        return {'REDMINE_URL': settings['redmine_url']}
    if service == 'kaiten':
        return {'KAITEN_BASE_URL': settings['kaiten_url']}
    raise ValueError(f'unknown service: {service}')
