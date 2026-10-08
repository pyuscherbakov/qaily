import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import keyring
import keyring.errors
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from qaily_launch import (  # noqa: E402
    MissingSecret,
    build_env,
    launch,
    main,
    render_headers,
    resolve_secret,
)


@pytest.fixture(autouse=True)
def clean_qaily_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("QAILY_"):
            monkeypatch.delenv(name)


def test_env_wins_over_keyring(monkeypatch):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", " from-env \n")
    monkeypatch.setattr(keyring, "get_password", lambda s, n: "from-keyring")
    assert resolve_secret("allure_token") == ("from-env", "env")


def test_empty_env_falls_through_to_keyring(monkeypatch):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", "")
    monkeypatch.setattr(keyring, "get_password", lambda s, n: "kr")
    assert resolve_secret("allure_token") == ("kr", "keyring")


def test_keyring_called_with_service_qaily(monkeypatch):
    calls = []
    monkeypatch.setattr(keyring, "get_password", lambda s, n: calls.append((s, n)) or None)
    assert resolve_secret("kaiten_api_token") == (None, "missing")
    assert calls == [("qaily", "kaiten_api_token")]


@pytest.mark.parametrize(
    "exc", [keyring.errors.NoKeyringError, keyring.errors.KeyringError, RuntimeError]
)
def test_keyring_failure_is_miss(monkeypatch, exc):
    def boom(service, name):
        raise exc("denied")

    monkeypatch.setattr(keyring, "get_password", boom)
    assert resolve_secret("allure_token") == (None, "missing")


def test_build_env_sets_secret_and_keeps_base(monkeypatch):
    monkeypatch.setenv("QAILY_REDMINE_API_KEY", "k")
    env = build_env(["REDMINE_API_KEY=redmine_api_key"], [], {"PATH": "/bin"})
    assert env == {"PATH": "/bin", "REDMINE_API_KEY": "k"}


def test_build_env_missing_required_raises_with_hint(monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    with pytest.raises(MissingSecret) as e:
        build_env(["KAITEN_TOKEN=kaiten_api_token"], [], {})
    assert str(e.value) == (
        "qaily: не найден токен kaiten_api_token. Задайте: uvx keyring set qaily "
        "kaiten_api_token (или переменную QAILY_KAITEN_API_TOKEN)"
    )


def test_build_env_optional_missing_is_skipped(monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    assert build_env(["CONTEXT7_API_KEY=context7_api_key?"], [], {}) == {}


def test_build_env_dir_expanded_created_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    env = build_env([], ["REDMINE_ALLOWED_DIRECTORIES=~/.qaily/redmine"], {})
    path = Path(env["REDMINE_ALLOWED_DIRECTORIES"])
    assert path.is_absolute() and path.is_dir() and path == tmp_path / ".qaily" / "redmine"


def test_render_headers_passes_braces_verbatim(monkeypatch):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", "a{b}c%$")
    assert render_headers(["Authorization=Api-Token {allure_token}"]) == {
        "Authorization": "Api-Token a{b}c%$"
    }


def test_launch_posix_execs_resolved_path(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda c, path=None: "/usr/bin/" + c)
    seen = {}
    monkeypatch.setattr(os, "execvpe", lambda f, a, e: seen.update(f=f, a=a))
    launch(["npx", "-y", "x"], {"PATH": "/usr/bin"})
    assert seen == {"f": "/usr/bin/npx", "a": ["/usr/bin/npx", "-y", "x"]}


def test_launch_windows_uses_subprocess_and_returns_code(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(shutil, "which", lambda c, path=None: r"C:\n\npx.cmd")
    monkeypatch.setattr(subprocess, "run", lambda a, env: SimpleNamespace(returncode=3, args=a))
    assert launch(["npx"], {"PATH": "x"}) == 3


def test_launch_unknown_command_is_clear_error(monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda c, path=None: None)
    assert launch(["nope"], {}) == 127
    assert "qaily: команда не найдена: nope" in capsys.readouterr().err


def test_main_missing_secret_exit_1_no_value_leak(monkeypatch, capsys):
    monkeypatch.setenv("QAILY_REDMINE_API_KEY", "SECRET-VALUE")
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    rc = main(
        ["run", "--secret", "A=redmine_api_key", "--secret", "B=kaiten_api_token", "--", "x"]
    )
    out = capsys.readouterr()
    assert rc == 1
    assert "SECRET-VALUE" not in out.out + out.err
    assert "kaiten_api_token" in out.err


def test_main_headers_prints_json(monkeypatch, capsys):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", "t")
    assert main(["headers", "Authorization=Api-Token {allure_token}"]) == 0
    assert json.loads(capsys.readouterr().out) == {"Authorization": "Api-Token t"}


def test_main_headers_missing_prints_nothing_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    assert main(["headers", "Authorization=Api-Token {allure_token}"]) == 1
    assert capsys.readouterr().out == ""
