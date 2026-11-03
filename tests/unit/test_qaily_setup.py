import json
import os
from pathlib import Path
import subprocess
import sys
import configparser

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bin'))

def load_settings(*args):
    from qaily_config import load_settings as func
    return func(*args)

def render_codex_fragment(*args, **kwargs):
    from qaily_setup import render_codex_fragment as func
    return func(*args, **kwargs)

ROOT = Path(__file__).resolve().parents[2]


def parse_fragment(fragment):
    # The generated subset is TOML tables and JSON-compatible scalar strings/booleans.
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(fragment)
    return {section: {key: json.loads(value) for key, value in parser.items(section)}
            for section in parser.sections()}


def package_root(path):
    helper = path / 'bin' / 'qaily_launch.py'
    helper.parent.mkdir(parents=True)
    helper.write_text('# fixture', encoding='utf-8')
    return path


def test_render_does_not_modify_user_config(tmp_path):
    home = tmp_path / 'home'
    config = home / '.codex' / 'config.toml'
    config.parent.mkdir(parents=True)
    original = b'# existing config\nmodel = "example"\n'
    config.write_bytes(original)
    result = subprocess.run([sys.executable, str(ROOT / 'bin/qaily_setup.py'), 'render', '--package-root', str(ROOT)], env={**os.environ, 'HOME': str(home)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert config.read_bytes() == original
    assert parse_fragment(result.stdout)['mcp_servers.qaily_testops']['default_tools_approval_mode'] == 'prompt'


def test_unicode_paths(tmp_path):
    root = package_root(tmp_path / 'Пакет с пробелами')
    fragment = render_codex_fragment(root, load_settings(tmp_path / 'absent'))
    config = parse_fragment(fragment)
    assert config['mcp_servers.qaily_testops.env_http_headers']['authorization'] == 'QAILY_TESTOPS_AUTHORIZATION'
    assert 'http_headers_helper' not in config['mcp_servers.qaily_testops']
    helper_config = parse_fragment(render_codex_fragment(root, load_settings(tmp_path / 'absent'), auth_mode='keyring-helper'))
    assert str(root / 'bin' / 'qaily_launch.py') in helper_config['mcp_servers.qaily_testops']['http_headers_helper']
    assert config['mcp_servers.qaily_testops']['url'] == 'https://astbroker.qatools.cloud/api/mcp'
    assert config['plugins."qaily@qaily-codex".mcp_servers.testops']['enabled'] is False


def test_repeat_render_no_duplicate_registration(tmp_path):
    settings = load_settings(tmp_path / 'absent')
    root = package_root(tmp_path / 'package')
    first = render_codex_fragment(root, settings)
    assert first == render_codex_fragment(root, settings)
    assert {key for key in parse_fragment(first) if key.startswith('mcp_servers.')} == {'mcp_servers.qaily_testops', 'mcp_servers.qaily_testops.env_http_headers'}


def test_render_rejects_deleted_installed_helper_without_touching_config(tmp_path):
    root = package_root(tmp_path / 'cache')
    (root / 'bin' / 'qaily_launch.py').unlink()
    settings = load_settings(tmp_path / 'absent')
    config = tmp_path / 'config.toml'
    config.write_text('existing = true\n', encoding='utf-8')
    with pytest.raises(ValueError, match='qaily_launch.py'):
        render_codex_fragment(root, settings, auth_mode='keyring-helper')
    assert 'env_http_headers' in render_codex_fragment(root, settings)
    assert config.read_text(encoding='utf-8') == 'existing = true\n'


def test_windows_helper_command_quotes_unicode_spaces_and_backslashes():
    from qaily_setup import format_helper_command
    path = r'C:\Users\Тест User\qaily\bin\qaily_launch.py'
    assert format_helper_command(path, windows=True) == (
        'uv run -q --script "C:\\Users\\Тест User\\qaily\\bin\\qaily_launch.py" '
        'headers "Authorization=Api-Token {allure}"'
    )
