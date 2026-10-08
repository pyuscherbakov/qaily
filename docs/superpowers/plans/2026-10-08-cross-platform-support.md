# Кросс-платформенная поддержка qaily — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** qaily работает в Claude Desktop и CLI на macOS/Windows и в CLI на Linux: секреты не через `userConfig`, пути и инструкции не привязаны к ОС.

**Architecture:** Python-лаунчер `bin/qaily_launch.py` (запуск через `uv run --script`, зависимость `keyring` inline) находит токены (`QAILY_*` → `keyring`), кладёт их в env MCP-сервера и запускает его; для http-сервера `testops` печатает заголовки через `headersHelper`. Режим `check` + скилл `/qaily:doctor` — диагностика.

**Tech Stack:** Python ≥3.10 stdlib + `keyring`, uv, pytest (только тесты), Claude Code plugin manifest.

**Spec:** `docs/superpowers/specs/2026-10-08-cross-platform-support-design.md`

## Global Constraints

- Имена серверов в `mcp-servers.json` не меняются (`testops`, `redmine`, `kaiten`, `context7`, `playwright`, `chrome-devtools`, `jam`).
- Сервис `keyring` — `qaily`; секреты: `allure_token`, `redmine_api_key`, `kaiten_api_token` (обязательные), `context7_api_key` (необязательный).
- Переменная секрета — `QAILY_<NAME в верхнем регистре>`, приоритет выше `keyring`.
- Каталог вложений Redmine — `~/.qaily/redmine`.
- Значения секретов никогда не пишутся в stdout/stderr (кроме stdout режима `headers`, который читает Claude Code).
- Текст ошибки отсутствующего секрета: `qaily: не найден токен <name>. Задайте: uvx keyring set qaily <name> (или переменную QAILY_<NAME>)`.
- Версии/пины серверов — текущие из `mcp-servers.json`.
- Версия плагина после работ — `0.4.0`; блок `userConfig` удалён.
- Коммиты — на русском, стиль репо `<область>: <что сделано>`, без `Co-Authored-By`.
- Комментарии в коде не пишем.

## Review Focus

1. **Windows-шимы `npx.cmd`/`uvx.exe`:** `subprocess` без shell не находит `.cmd` по `PATHEXT` → лаунчер резолвит `cmd[0]` через `shutil.which` с `PATH` из итогового env; при промахе — понятная ошибка, не traceback (тест в Task 1). Это же причина, по которой `playwright` и `chrome-devtools` тоже идут через лаунчер (Claude Code на Windows не запускает `npx` без `cmd /c`) — **отступление от спеки**, где они «без изменений».
2. **Пустая переменная `QAILY_X=""`** считается незаданной и не перекрывает `keyring` (тест в Task 1).
3. **Исключение бэкенда `keyring`** (отказ в доступе к Keychain, `KeyringError`, `NoKeyringError`) — промах с сообщением, не traceback (тест в Task 1).
4. **Фигурные скобки и спецсимволы в значении токена** в `headers` переходят в заголовок дословно (тест в Task 1).
5. **Обратные слэши `${CLAUDE_PLUGIN_ROOT}` на Windows** в строке `headersHelper` (её исполняет shell) — путь в двойных кавычках (Task 2, проверка — чек-лист Windows в Task 7).

---

### Task 1: Лаунчер — секреты, env, заголовки, запуск

**Files:**
- Create: `bin/qaily_launch.py`
- Test: `bin/test_qaily_launch.py`

**Interfaces:**
- Produces (CLI, используется в Task 2, 4):
  - `qaily_launch.py run [--secret ENV=name[?]]... [--dir ENV=~/path]... -- <cmd> <args>`
  - `qaily_launch.py headers "<Header>=<шаблон с {name}>"...`
- Produces (Python, используется в Task 4):
  - `SERVICE = "qaily"`
  - `class MissingSecret(Exception)` с атрибутом `name: str`; `str(exc)` — текст из Global Constraints
  - `resolve_secret(name: str) -> tuple[str | None, str]` — `(значение, источник)`, источник ∈ `"env"`, `"keyring"`, `"missing"`
  - `build_env(secrets: list[str], dirs: list[str], base: Mapping[str, str]) -> dict[str, str]` — бросает `MissingSecret`
  - `render_headers(specs: list[str]) -> dict[str, str]` — бросает `MissingSecret`
  - `launch(cmd: list[str], env: dict[str, str]) -> int`
  - `main(argv: list[str] | None = None) -> int`

Шапка файла — PEP 723: `requires-python = ">=3.10"`, `dependencies = ["keyring==25.6.0"]`.
Тесты: `uv run --with pytest --with keyring==25.6.0 pytest bin -q`. В тестах `keyring.get_password` подменяется `monkeypatch`, переменные `QAILY_*` чистятся фикстурой `autouse`.

- [ ] **Step 1: Тесты поиска секрета**

```python
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

@pytest.mark.parametrize("exc", [keyring.errors.NoKeyringError, keyring.errors.KeyringError, RuntimeError])
def test_keyring_failure_is_miss(monkeypatch, exc):
    def boom(s, n): raise exc("denied")
    monkeypatch.setattr(keyring, "get_password", boom)
    assert resolve_secret("allure_token") == (None, "missing")
```

- [ ] **Step 2: Запустить — FAIL** (`ModuleNotFoundError`/`ImportError` на `qaily_launch`)

- [ ] **Step 3: Реализовать `SERVICE`, `MissingSecret`, `resolve_secret`** — `strip()` значения, пустое = нет, любое исключение `keyring` = промах.

- [ ] **Step 4: Тесты `build_env` и `render_headers`**

```python
def test_build_env_sets_secret_and_keeps_base(monkeypatch):
    monkeypatch.setenv("QAILY_REDMINE_API_KEY", "k")
    env = build_env(["REDMINE_API_KEY=redmine_api_key"], [], {"PATH": "/bin"})
    assert env == {"PATH": "/bin", "REDMINE_API_KEY": "k"}

def test_build_env_missing_required_raises_with_hint(monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    with pytest.raises(MissingSecret) as e:
        build_env(["KAITEN_TOKEN=kaiten_api_token"], [], {})
    assert str(e.value) == "qaily: не найден токен kaiten_api_token. Задайте: uvx keyring set qaily kaiten_api_token (или переменную QAILY_KAITEN_API_TOKEN)"

def test_build_env_optional_missing_is_skipped(monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    assert build_env(["CONTEXT7_API_KEY=context7_api_key?"], [], {}) == {}

def test_build_env_dir_expanded_created_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    env = build_env([], ["REDMINE_ALLOWED_DIRECTORIES=~/.qaily/redmine"], {})
    p = Path(env["REDMINE_ALLOWED_DIRECTORIES"])
    assert p.is_absolute() and p.is_dir() and p == tmp_path / ".qaily" / "redmine"

def test_render_headers_passes_braces_verbatim(monkeypatch):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", "a{b}c%$")
    assert render_headers(["Authorization=Api-Token {allure_token}"]) == {"Authorization": "Api-Token a{b}c%$"}
```

- [ ] **Step 5: Запустить — FAIL**, реализовать `build_env`, `render_headers` (подстановка `{name}` через `re.sub(r"\{(\w+)\}", ...)`, не `str.format` — значение не должно интерпретироваться), запустить — PASS.

- [ ] **Step 6: Тесты `launch` и `main`**

```python
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
    rc = main(["run", "--secret", "A=redmine_api_key", "--secret", "B=kaiten_api_token", "--", "x"])
    out = capsys.readouterr()
    assert rc == 1 and "SECRET-VALUE" not in out.out + out.err and "kaiten_api_token" in out.err

def test_main_headers_prints_json(monkeypatch, capsys):
    monkeypatch.setenv("QAILY_ALLURE_TOKEN", "t")
    assert main(["headers", "Authorization=Api-Token {allure_token}"]) == 0
    assert json.loads(capsys.readouterr().out) == {"Authorization": "Api-Token t"}

def test_main_headers_missing_prints_nothing_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(keyring, "get_password", lambda s, n: None)
    assert main(["headers", "Authorization=Api-Token {allure_token}"]) == 1
    assert capsys.readouterr().out == ""
```

- [ ] **Step 7: Запустить — FAIL**, реализовать `launch` (`shutil.which(cmd[0], path=env.get("PATH"))`; POSIX — `os.execvpe`, `win32` — `subprocess.run(...).returncode`) и `main` (`argparse`, подкоманды `run`/`headers`; `run` берёт команду после `--`; `MissingSecret` → stderr, код 1). `if __name__ == "__main__": sys.exit(main())`. Запустить — PASS.

- [ ] **Step 8: Коммит**

```bash
git add bin/qaily_launch.py bin/test_qaily_launch.py
git commit -m "Лаунчер MCP-серверов: секреты из QAILY_* и keyring, заголовки, запуск на всех ОС"
```

---

### Task 2: Подключение лаунчера к серверам + проверка на Mac (этап 0)

**Files:**
- Modify: `mcp-servers.json` (все серверы, кроме `jam`)
- Modify: `.claude-plugin/plugin.json` (удалить `userConfig`, `version` → `0.4.0`)

**Interfaces:**
- Consumes: CLI лаунчера из Task 1.
- Produces: префикс запуска `"command": "uv", "args": ["run", "--script", "${CLAUDE_PLUGIN_ROOT}/bin/qaily_launch.py", "run", ...]` — им пользуются все stdio-серверы.

- [ ] **Step 1: Переписать `mcp-servers.json`** по таблице спеки (раздел «`mcp-servers.json`»). Аргументы лаунчера:
  - `redmine`: `--secret REDMINE_API_KEY=redmine_api_key --dir REDMINE_ALLOWED_DIRECTORIES=~/.qaily/redmine -- uvx --from mcp-redmine==2026.09.10.084818 mcp-redmine`; `env` без `REDMINE_API_KEY` и `REDMINE_ALLOWED_DIRECTORIES`.
  - `kaiten`: `--secret KAITEN_TOKEN=kaiten_api_token -- uvx --from git+https://github.com/pyuscherbakov/kaiten-mcp@8d3c666 kaiten-mcp`; `env` без `KAITEN_TOKEN`.
  - `context7`: `--secret CONTEXT7_API_KEY=context7_api_key? -- npx -y @upstash/context7-mcp@4.1.1`; `env` удалить.
  - `playwright`, `chrome-devtools`: `-- npx -y <пакет@версия>` без секретов (Review Focus 1).
  - `testops`: убрать `headers`, добавить `"headersHelper": "uv run --script \"${CLAUDE_PLUGIN_ROOT}/bin/qaily_launch.py\" headers \"Authorization=Api-Token {allure_token}\""`.
- [ ] **Step 2: `plugin.json`** — удалить `userConfig`, `version: "0.4.0"`. Проверка: `python3 -m json.tool` по обоим файлам без ошибок.
- [ ] **Step 3: CLI на Mac.** Токены в `keyring` кладёт пользователь (`uvx keyring set qaily …`). Run: `claude --plugin-dir . mcp list`. Expected: `testops`, `redmine`, `kaiten`, `context7`, `playwright`, `chrome-devtools` — `Connected`.
- [ ] **Step 4: Desktop на Mac.** Пользователь включает плагин из ветки (`/plugin marketplace add <путь к ветке>` или `--plugin-dir`) и открывает новую Code-сессию; там `ToolSearch` по `testops`, `redmine`, `kaiten` находит инструменты `mcp__plugin_qaily_*`. Зафиксировать: был ли диалог Keychain, время первого старта.
- [ ] **Step 5 (только если `testops` не подключился в Step 3/4):** заменить `testops` на stdio-прокси `run --secret QAILY_AUTH=allure_token -- npx -y mcp-remote@<текущая версия> https://astbroker.qatools.cloud/api/mcp --header "Authorization:Api-Token ${QAILY_AUTH}"` (форма заголовка — по README `mcp-remote`), повторить Step 3–4.
- [ ] **Step 6: Коммит**

```bash
git add mcp-servers.json .claude-plugin/plugin.json
git commit -m "MCP-серверы через лаунчер, userConfig удалён, версия 0.4.0"
```

---

### Task 3: Каталог вложений Redmine `~/.qaily/redmine`

**Files:**
- Modify: `agents/doc-researcher.md`, `agents/failure-analyst.md`, `agents/autotest-reviewer.md` (все вхождения `/tmp/qaily-redmine`)
- Modify: `settings.local.json.example`

- [ ] **Step 1: Проверить зафиксированную версию `mcp-redmine`.** Run: `uvx --from mcp-redmine==2026.09.10.084818 python -c "import inspect, mcp_redmine.server as s; print('expanduser' in inspect.getsource(s.validate_path))"`. Expected: `True`. Если `False` — остановиться и вернуться к пользователю.
- [ ] **Step 2: Агенты.** `save_path: "~/.qaily/redmine/<id задачи>/<attachment_id>-<filename>"`; после скачивания читать файл по `saved_to` из ответа `redmine_download`; ограничения «только в `/tmp/qaily-redmine/`» → «только в `~/.qaily/redmine/`». Проверка: `grep -rn "tmp/qaily-redmine" agents skills` — пусто.
- [ ] **Step 3: `settings.local.json.example`** — `Read(//tmp/qaily-redmine/**)` и `Read(//private/tmp/qaily-redmine/**)` → один `Read(~/.qaily/redmine/**)`. Проверка: `python3 -m json.tool settings.local.json.example`.
- [ ] **Step 4: Ручная проверка на Mac:** в сессии с плагином попросить `doc-researcher` разобрать задачу Redmine с PDF-вложением — файл появился в `~/.qaily/redmine/<id>/`, агент его прочитал.
- [ ] **Step 5: Коммит** — `Вложения Redmine в ~/.qaily/redmine вместо /tmp`.

---

### Task 4: Режим `check` и скилл `/qaily:doctor`

**Files:**
- Modify: `bin/qaily_launch.py`, `bin/test_qaily_launch.py`
- Create: `skills/doctor/SKILL.md`

**Interfaces:**
- Consumes: `resolve_secret` из Task 1.
- Produces: `qaily_launch.py check` — по строке на секрет: `<name>: <источник> — <результат>`; код выхода 0, если все обязательные найдены и ни один не получил `401/403`, иначе 1.

Проверочные запросы (`urllib.request`, таймаут 10 с):

| Секрет | URL | Заголовок |
|---|---|---|
| `allure_token` | `https://astbroker.qatools.cloud/api/rs/project` | `Authorization: Api-Token <t>` |
| `redmine_api_key` | `https://redmine.fast-system.ru/users/current.json` | `X-Redmine-API-Key: <t>` |
| `kaiten_api_token` | `https://lab-company.kaiten.ru/api/latest/users/current` | `Authorization: Bearer <t>` |
| `context7_api_key` | — (только источник) | — |

Результат: `HTTP <код>` либо `сеть: <класс исключения>`; для `missing` — подсказка из `MissingSecret`.

- [ ] **Step 1: Тесты** (`urllib.request.urlopen` подменён):
  - `test_check_all_ok_exit_0` — все секреты из env, ответы 200 → код 0, в выводе `allure_token: env — HTTP 200`.
  - `test_check_401_exit_1` — `HTTPError(401)` для redmine → код 1, строка `redmine_api_key: keyring — HTTP 401`.
  - `test_check_missing_required_shows_hint` — нет `kaiten_api_token` → код 1, в выводе `uvx keyring set qaily kaiten_api_token`.
  - `test_check_optional_missing_exit_0` — нет `context7_api_key`, остальные 200 → код 0.
  - `test_check_never_prints_values` — значения секретов отсутствуют в stdout/stderr.
- [ ] **Step 2: FAIL → реализовать `check` → PASS** (`uv run --with pytest --with keyring==25.6.0 pytest bin -q`).
- [ ] **Step 3: `skills/doctor/SKILL.md`** — frontmatter `name: doctor`, `description` (рус.: «Диагностика qaily: проверяет токены TestOps/Redmine/Kaiten/Context7 и доступ к сервисам. Use when пользователь пишет /qaily:doctor, «qaily не работает», «нет инструментов testops/redmine/kaiten»…»). Тело: выполнить `uv run --script "${CLAUDE_PLUGIN_ROOT}/bin/qaily_launch.py" check`, пересказать по строкам, для каждого промаха дать команду из вывода, для `401` — «токен неверный или отозван, перевыпустить и `uvx keyring set …`», напомнить перезапустить сессию после правок. Значения токенов не запрашивать и не выводить.
- [ ] **Step 4: Ручная проверка на Mac:** в CLI-сессии с `--plugin-dir .` вызвать `/qaily:doctor` — отчёт по 4 секретам.
- [ ] **Step 5: Коммит** — `Диагностика: режим check и скилл /qaily:doctor`.

---

### Task 5: README для трёх ОС

**Files:**
- Modify: `README.md` (разделы «Установка», «Проверка токенов вручную», «Если что-то не работает», блок `GITLAB_TOKEN` в «Ревью автотестов»)

Содержание — раздел спеки «Онбординг, миграция, README» без изменений: таблица пререквизитов по ОС, пометка «Desktop — macOS и Windows, Linux — CLI», команды `uvx keyring set`, `QAILY_*` для Linux без Secret Service, новый подраздел «Обновление с 0.3.x», `/qaily:doctor` вместо `curl`, `GITLAB_TOKEN` — `export` и `setx`, пункты troubleshooting (диалог Keychain «Всегда разрешать», Secret Service, медленный первый запуск `uv`). Если в Task 2 Step 4 диалога Keychain не было — пункт про него не добавлять.

- [ ] **Step 1: Переписать разделы.**
- [ ] **Step 2: Проверка:** `grep -n 'user_config\|/tmp/qaily\|ALLURE_TOKEN\b' README.md` — пусто; каждая команда из README есть в спеке или в `mcp-servers.json`.
- [ ] **Step 3: Коммит** — `README: установка на macOS, Windows и Linux, миграция с 0.3.x`.

---

### Task 6: Проверка Linux в Docker (этап 2)

Файлов не создаёт — только проверка.

- [ ] **Step 1: Образ:** `docker run --rm -it -v "$PWD":/qaily -w /qaily node:20-bookworm bash`, внутри: установка `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`), `npm i -g @anthropic-ai/claude-code`, `git`.
- [ ] **Step 2: Тесты лаунчера в контейнере:** `uv run --with pytest --with keyring==25.6.0 pytest bin -q` — PASS.
- [ ] **Step 3: Пользователь** запускает контейнер с `-e QAILY_ALLURE_TOKEN -e QAILY_REDMINE_API_KEY -e QAILY_KAITEN_API_TOKEN` (значения из своего окружения; агент токены не читает). Expected: `uv run --script bin/qaily_launch.py check` — три `HTTP 200`, источник `env`; `claude --plugin-dir /qaily mcp list` — 6 stdio/http серверов `Connected`.
- [ ] **Step 4: Результат** (что подключилось, время первого старта) — в отчёт пользователю; при падениях — фикс по образцу Task 7 Step 3.

---

### Task 7: Чек-лист Windows и прогон на VM (этап 3)

**Files:**
- Create: `docs/windows-checklist.md` — таблица «№ · шаг · ожидаемое · факт · ок?»

Шаги — этап 3 спеки (пункты 1–6) плюс:
- `/qaily:doctor` в CLI и Desktop;
- `testops` подключён (проверка кавычек пути `headersHelper`, Review Focus 5);
- `playwright` и `chrome-devtools` подключены (Review Focus 1);
- после закрытия сессии в «Диспетчере задач» нет оставшихся `node.exe`/`python.exe` от qaily.

- [ ] **Step 1: Написать чек-лист, коммит** — `Чек-лист прогона на Windows`.
- [ ] **Step 2: Пользователь прогоняет чек-лист на Windows-VM**, заполняет «факт».
- [ ] **Step 3: По каждому упавшему шагу** — `superpowers:systematic-debugging`, фикс с тестом в `bin/test_qaily_launch.py`, если затронут лаунчер; коммит на фикс; повторный прогон упавших шагов пользователем.

---

### Task 8: Регресс на macOS и миграция (этап 4)

- [ ] **Step 1: Миграция:** на Mac установить qaily 0.3.5 из `main` (с настроенным `userConfig`), обновить до ветки, выполнить `uvx keyring set` ×3 — в CLI и Desktop все серверы подключены, `/qaily:doctor` зелёный.
- [ ] **Step 2: Сокращённый чек-лист** из `docs/windows-checklist.md` (шаги 4–6) в CLI и Desktop на Mac.
- [ ] **Step 3: Тесты** `uv run --with pytest --with keyring==25.6.0 pytest bin -q` — PASS; `git status` чистый.
