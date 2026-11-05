import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bin'))

@pytest.fixture(autouse=True)
def config_module():
    global load_settings, service_env
    from qaily_config import load_settings, service_env


def test_defaults_and_overrides(tmp_path):
    settings_file = tmp_path / 'settings.json'
    assert load_settings(settings_file)['testops_url'] == 'https://astbroker.qatools.cloud'
    settings_file.write_text('{"redmine_url":"http://127.0.0.1:8765/base/"}', encoding='utf-8')
    settings = load_settings(settings_file)
    assert settings['testops_url'] == 'https://astbroker.qatools.cloud'
    assert service_env('redmine', settings) == {'REDMINE_URL': 'http://127.0.0.1:8765/base'}


@pytest.mark.parametrize('contents', [
    '{"token":"fixture-secret"}', '{"other":"fixture-secret"}',
    '{"redmine_url":"http://user:fixture-secret@localhost"}',
    '{"redmine_url":"http://localhost/?token=fixture-secret"}',
    '{"redmine_url":"file:///tmp/a"}', '{"redmine_url":123}', '{bad fixture-secret',
    '[]',
])
def test_reject_secret_or_unknown_config_keys(tmp_path, contents):
    path = tmp_path / 'config.json'
    path.write_text(contents, encoding='utf-8')
    with pytest.raises(ValueError) as error:
        load_settings(path)
    assert 'fixture-secret' not in str(error.value)
    assert 'config' in str(error.value).lower()
