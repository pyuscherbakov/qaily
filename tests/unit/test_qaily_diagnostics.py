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
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: ('HTTP 200', True))
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
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: ('HTTP 403', False))
    assert 'прав' in diagnostics.format_checks(diagnostics.token_checks(load_settings(tmp_path / 'missing')))


def test_applied_config_stale_helper_and_untrusted_error(monkeypatch, tmp_path):
    import sys
    config = tmp_path / 'config.toml'
    config.write_text('[mcp_servers.qaily_testops]\nhttp_headers_helper = "uv run --script /missing/qaily_launch.py"\n')
    result = diagnostics.applied_config_check(config)[0]
    assert result.status == ('error' if sys.version_info >= (3, 11) else 'not_checked')
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('SECRET_CANARY', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: ('сеть: SECRET_CANARY', False))
    assert 'SECRET_CANARY' not in diagnostics.format_checks(diagnostics.token_checks(load_settings(tmp_path / 'missing')))


@pytest.mark.parametrize('script', [r'C:\qaily\bin\qaily_launch.py', r'C:\Users\Test User\qaily\bin\qaily_launch.py'])
def test_applied_config_preserves_windows_helper_path(monkeypatch, tmp_path, script):
    import json
    import subprocess
    import sys
    if sys.version_info < (3, 11):
        pytest.skip('tomllib unavailable')
    command = subprocess.list2cmdline(['uv', 'run', '--script', script, 'headers', 'Authorization=Api-Token {allure}'])
    config = tmp_path / 'config.toml'
    config.write_text('[mcp_servers.qaily_testops]\nhttp_headers_helper = ' + json.dumps(command) + '\n')
    seen = []
    monkeypatch.setattr(Path, 'is_file', lambda path: seen.append(str(path)) or str(path) == script)
    assert diagnostics.applied_config_check(config)[0].status == 'ok'
    assert seen == [script]


@pytest.mark.parametrize('value', ['"SECRET_CANARY"', '[]', '42'])
def test_applied_config_rejects_non_table_servers_without_leaking(tmp_path, value):
    import sys
    config = tmp_path / 'config.toml'
    config.write_text('mcp_servers = ' + value + '\n')
    result = diagnostics.applied_config_check(config)[0]
    assert result.status == ('error' if sys.version_info >= (3, 11) else 'not_checked')
    assert 'SECRET_CANARY' not in diagnostics.format_checks([result])


def _applied_config(path, *, url='https://astbroker.qatools.cloud/api/mcp', auth='env', bundled=False):
    import json
    from qaily_setup import format_helper_command
    path.write_text('[plugins."qaily@qaily-codex".mcp_servers.testops]\nenabled = ' + str(bundled).lower() + '\n'
                    '[mcp_servers.qaily_testops]\nurl = ' + json.dumps(url) + '\n' +
                    ('[mcp_servers.qaily_testops.env_http_headers]\nAuthorization = "QAILY_TESTOPS_AUTHORIZATION"\n'
                     if auth == 'env' else 'http_headers_helper = ' + json.dumps(format_helper_command(str(Path(diagnostics.__file__).parent / 'qaily_launch.py'), windows=False)) + '\n'))


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_native_header_selected_even_with_raw_secret(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    seen = []
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('RAW_CANARY', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: (seen.append((args, kwargs)) or 'HTTP 200', True))
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config, {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token NATIVE_CANARY'})
    assert result.status == 'ok' and 'env-header' in result.detail
    assert seen[0][0][2] == 'Api-Token NATIVE_CANARY'
    assert seen[0][1] == {'follow_redirects': False}
    assert 'CANARY' not in diagnostics.format_checks([result])


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_auth_missing_or_environment_unknown_never_uses_raw(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('RAW_CANARY', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    settings = load_settings(tmp_path / 'missing')
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'error'
    assert diagnostics.codex_testops_check(settings, config, None).status == 'not_checked'


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_helper_uses_raw_token_only_when_configured(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config, auth='helper')
    seen = []
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: ('RAW_CANARY', 'env'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: (seen.append((args, kwargs)) or 'HTTP 200', True))
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config, {'QAILY_TESTOPS_AUTHORIZATION': 'NATIVE_CANARY'})
    assert result.status == 'ok' and 'keyring-helper' in result.detail
    assert seen[0][0][2] == 'Api-Token RAW_CANARY'
    assert seen[0][1] == {'follow_redirects': False}


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_mismatch_duplicate_bundled_and_bad_config_never_probe(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    settings = load_settings(tmp_path / 'missing')
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    _applied_config(config, url='https://other.invalid/api/mcp')
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'not_checked'
    _applied_config(config, bundled=True)
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'error'
    config.write_text('[plugins."qaily@qaily-codex".mcp_servers.testops]\nenabled = true\n')
    settings['testops_url'] = 'https://other.invalid'
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'not_checked'
    config.write_text('[bad')
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'error'


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_native_only_and_unknown_parser(tmp_path, monkeypatch):
    import builtins
    config = tmp_path / 'config.toml'
    _applied_config(config)
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: (None, 'missing'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: ('HTTP 200', True))
    settings = load_settings(tmp_path / 'missing')
    assert diagnostics.codex_testops_check(settings, config, {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'}).status == 'ok'
    original = builtins.__import__
    def no_tomllib(name, *args, **kwargs):
        if name == 'tomllib':
            raise ImportError
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_tomllib)
    assert diagnostics.codex_testops_check(settings, config, {}).status == 'not_checked'


def test_other_service_checks_can_skip_legacy_allure(tmp_path, monkeypatch):
    names = []
    monkeypatch.setattr(diagnostics, 'resolve_secret', lambda name: (names.append(name) or None, 'missing'))
    diagnostics.token_checks(load_settings(tmp_path / 'missing'), skip_allure=True)
    assert 'allure' not in names and {'redmine', 'kaiten', 'context7'} <= set(names)


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_cli_exposes_not_checked_status_without_process_env(tmp_path, monkeypatch, capsys):
    import qaily_launch
    config = tmp_path / 'config.toml'
    _applied_config(config)
    monkeypatch.setattr(qaily_launch, 'load_settings', lambda: load_settings(tmp_path / 'missing'))
    monkeypatch.setattr(diagnostics, 'token_checks', lambda *args, **kwargs: [])
    assert qaily_launch.main(['check-codex', '--config', str(config)]) == 0
    assert 'not_checked' in capsys.readouterr().out


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_invalid_enabled_flag_does_not_probe(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    config.write_text(config.read_text().replace('[mcp_servers.qaily_testops]\n', '[mcp_servers.qaily_testops]\nenabled = "true"\n'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    assert diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config, {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'}).status in ('error', 'not_checked')


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_conflicting_auth_setting_is_not_probed(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    config.write_text(config.read_text().replace('[mcp_servers.qaily_testops]\n', '[mcp_servers.qaily_testops]\nbearer_token_env_var = "OTHER"\n'))
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    assert diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config, {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'}).status == 'not_checked'


def test_codex_http_probe_rejects_redirect_without_forwarding_header(monkeypatch):
    import qaily_launch
    import urllib.error
    import urllib.request
    seen = []
    def opener(handler):
        assert handler.redirect_request(None, None, 302, 'redirect', {}, 'https://other.invalid') is None
        class FakeOpener:
            def open(self, request, timeout):
                seen.append(request.full_url)
                raise urllib.error.HTTPError(request.full_url, 302, 'redirect', {}, None)
        return FakeOpener()
    monkeypatch.setattr(urllib.request, 'build_opener', opener)
    assert qaily_launch.probe('https://example.invalid/api', 'Authorization', 'CANARY', follow_redirects=False) == ('HTTP 302', False)
    assert seen == ['https://example.invalid/api']


def test_codex_unavailable_toml_parser_is_not_checked(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def no_tomllib(name, *args, **kwargs):
        if name == 'tomllib':
            raise ImportError
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_tomllib)
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), tmp_path / 'config.toml', None)
    assert result.status == 'not_checked' and 'parser' in result.detail


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
@pytest.mark.parametrize('other_url', [
    'https://astbroker.qatools.cloud/api/mcp',
    'https://ASTBROKER.qatools.cloud:443/api/mcp/',
])
def test_codex_other_active_registration_for_same_url_never_probes(tmp_path, monkeypatch, other_url):
    import json
    config = tmp_path / 'config.toml'
    _applied_config(config)
    with config.open('a') as stream:
        stream.write('\n[mcp_servers.testops_copy]\nurl = ' + json.dumps(other_url) + '\n')
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config,
                                              {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'})
    assert result.status in ('error', 'not_checked')
    assert 'CANARY' not in result.detail and 'astbroker' not in result.detail


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_other_disabled_registration_does_not_block_probe(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    with config.open('a') as stream:
        stream.write('\n[mcp_servers.testops_copy]\nenabled = false\nurl = "https://ASTBROKER.qatools.cloud:443/api/mcp/"\n')
    seen = []
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: (seen.append(True) or 'HTTP 200', True))
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config,
                                              {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'})
    assert result.status == 'ok' and len(seen) == 1


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_uninspectable_other_registration_is_not_checked(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    with config.open('a') as stream:
        stream.write('\n[mcp_servers.unknown]\ncommand = "unknown-command"\n')
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: pytest.fail('must not probe'))
    result = diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config,
                                              {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'})
    assert result.status == 'not_checked'


@pytest.mark.skipif(sys.version_info < (3, 11), reason='tomllib unavailable')
def test_codex_other_distinct_http_registration_does_not_block_probe(tmp_path, monkeypatch):
    config = tmp_path / 'config.toml'
    _applied_config(config)
    with config.open('a') as stream:
        stream.write('\n[mcp_servers.other]\nurl = "https://other.invalid/api/mcp"\n')
    monkeypatch.setattr(diagnostics, 'probe', lambda *args, **kwargs: ('HTTP 200', True))
    assert diagnostics.codex_testops_check(load_settings(tmp_path / 'missing'), config,
                                           {'QAILY_TESTOPS_AUTHORIZATION': 'Api-Token CANARY'}).status == 'ok'
