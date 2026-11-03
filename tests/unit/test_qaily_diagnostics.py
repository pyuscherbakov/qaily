import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bin'))
import qaily_diagnostics as diagnostics
from qaily_config import load_settings


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: (None, 'missing'))


def test_http_ok_is_not_mcp_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('SECRET_CANARY', 'env') if name == 'allure' else (None, 'missing'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args: ('HTTP 200', True))
    results = diagnostics.token_checks(load_settings(tmp_path / 'missing'))
    assert any(r.name == 'allure' and r.layer == 'http' and r.status == 'ok' for r in results)
    assert not any(r.layer == 'mcp' and r.status == 'ok' for r in results)
    assert 'SECRET_CANARY' not in diagnostics.format_checks(results)


def test_static_policy_is_not_enforcement_proof():
    result = diagnostics.static_policy_check(True)
    assert result.layer == 'policy' and result.status == 'not_checked'


def test_override_probe_same_service(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('x', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda url, *args: (seen.append(url) or 'HTTP 200', True))
    settings = load_settings(tmp_path / 'missing')
    settings['testops_url'] = 'http://example.invalid/base'
    diagnostics.token_checks(settings)
    assert seen[0] == 'http://example.invalid/base/api/rs/project'


def test_no_secret_in_failures(monkeypatch, tmp_path):
    monkeypatch.setenv('QAILY_ALLURE', 'SECRET_CANARY')
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('SECRET_CANARY', 'env'))
    def fail(*args):
        raise RuntimeError('SECRET_CANARY https://host/?secret=SECRET_CANARY')
    monkeypatch.setattr(diagnostics, 'probe', fail)
    assert 'SECRET_CANARY' not in diagnostics.format_checks(diagnostics.token_checks(load_settings(tmp_path / 'missing')))


def test_403_is_not_always_revoked_token(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('x', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args: ('HTTP 403', False))
    assert 'прав' in diagnostics.format_checks(diagnostics.token_checks(load_settings(tmp_path / 'missing')))


def test_applied_config_stale_helper_and_untrusted_error(monkeypatch, tmp_path):
    import sys
    config = tmp_path / 'config.toml'
    config.write_text('[mcp_servers.qaily_testops]\nhttp_headers_helper = "uv run --script /missing/qaily_launch.py"\n')
    result = diagnostics.applied_config_check(config)[0]
    assert result.status == ('error' if sys.version_info >= (3, 11) else 'not_checked')
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('SECRET_CANARY', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args: ('сеть: SECRET_CANARY', False))
    assert 'SECRET_CANARY' not in diagnostics.format_checks(diagnostics.token_checks(load_settings(tmp_path / 'missing')))
