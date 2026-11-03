import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bin'))

def load_settings(*args):
    from qaily_config import load_settings as func
    return func(*args)

def render_codex_fragment(*args):
    from qaily_setup import render_codex_fragment as func
    return func(*args)

ROOT = Path(__file__).resolve().parents[2]


def test_render_does_not_modify_user_config(tmp_path):
    home = tmp_path / 'home'
    config = home / '.codex' / 'config.toml'
    config.parent.mkdir(parents=True)
    original = b'# existing config\nmodel = "example"\n'
    config.write_bytes(original)
    result = subprocess.run([sys.executable, str(ROOT / 'bin/qaily_setup.py'), 'render', '--package-root', str(ROOT)], env={**os.environ, 'HOME': str(home)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert config.read_bytes() == original
    assert tomllib.loads(result.stdout)['mcp_servers']['qaily_testops']['default_tools_approval_mode'] == 'prompt'


def test_windows_and_unicode_paths(tmp_path):
    root = tmp_path / 'Пакет с пробелами'
    fragment = render_codex_fragment(root, load_settings(tmp_path / 'absent'))
    config = tomllib.loads(fragment)
    helper = config['mcp_servers']['qaily_testops']['http_headers_helper']
    assert str(root / 'bin' / 'qaily_launch.py') in helper
    assert config['mcp_servers']['qaily_testops']['url'] == 'https://astbroker.qatools.cloud/api/mcp'
    assert config['plugins']['qaily@qaily-codex']['mcp_servers']['testops']['enabled'] is False


def test_repeat_render_no_duplicate_registration(tmp_path):
    settings = load_settings(tmp_path / 'absent')
    first = render_codex_fragment(tmp_path, settings)
    assert first == render_codex_fragment(tmp_path, settings)
    assert set(tomllib.loads(first)['mcp_servers']) == {'qaily_testops'}
