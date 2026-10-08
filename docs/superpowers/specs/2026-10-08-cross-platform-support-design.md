# Кросс-платформенная поддержка qaily (Desktop + CLI, macOS / Linux / Windows)

Дата: 2026-10-08 · Версия плагина после работ: 0.4.0 (ломающее изменение для пользователей)

## Цель

qaily полностью работает в Claude Desktop (Code tab) и Claude Code CLI на macOS, Linux и Windows:
все MCP-серверы подключаются, все скиллы проходят сценарий, установка одинаково понятна на
каждой ОС. Claude Desktop официально есть только для macOS и Windows, на Linux qaily
используется через CLI.

## Контекст и причина

- В Desktop не стартуют серверы `testops`, `redmine`, `kaiten`: подстановка
  `${user_config.*}` для плагинов там не работает (anthropics/claude-code#89749, #88529,
  вероятный механизм — #90753: при `--plugin-dir` конфиг ищется под ключом `qaily`, а хранится
  под `qaily@qaily`). Серверы без обязательного `userConfig` стартуют.
- На Windows дополнительно сломан каталог вложений Redmine `/tmp/qaily-redmine`
  (`mcp-servers.json`, агенты `doc-researcher`, `failure-analyst`, `autotest-reviewer`,
  маски в `settings.local.json.example`).
- README описывает установку только для macOS/Linux, `GITLAB_TOKEN` — только через `export`.
- Скиллы выполняют команды через Bash-инструмент Claude Code; на Windows это Git Bash
  (обязательная зависимость Claude Code), поэтому `curl` и `$GITLAB_TOKEN` в `review-autotest`
  менять не нужно.

## Решения

| Вопрос | Решение |
|---|---|
| Объём | Полная поддержка Windows, включая прогон всех скиллов |
| Проверка Windows | Windows-VM на Mac, ручной прогон по чек-листу; CI не делаем |
| Хранение токенов | Системное хранилище через `keyring`, запасной путь — переменные `QAILY_*` |
| `userConfig` | Удаляется целиком; `context7` переезжает на тот же механизм |
| Механизм | Python-лаунчер через `uv run --script` (без shell, `uv` уже в пререквизитах) |
| Диагностика | Режим `check` + скилл `/qaily:doctor` |

Отклонены: shell-обёртки под каждую ОС (две реализации, на Windows нет штатного чтения
секрета из Credential Manager), Node-лаунчер (нативный модуль `keyring` под каждую
ОС/архитектуру — лишняя точка отказа), `userConfig` как необязательный источник с приоритетом
(два места хранения одного токена, CLI и Desktop могут разойтись).

## Компоненты

### Лаунчер `bin/qaily_launch.py`

Один файл, зависимость `keyring` объявлена inline (PEP 723). Не знает о конкретных серверах:
что запускать и какие секреты подставлять, задаёт `mcp-servers.json`.

```
qaily_launch.py run [--secret ENV=name[?]]... [--dir ENV=~/path]... -- <команда> <аргументы>
qaily_launch.py headers "<Header>=<шаблон с {name}>"...
qaily_launch.py check
```

- `--secret ENV=name` — найти секрет `name`, положить в переменную `ENV` процесса сервера.
  Суффикс `?` — секрет необязательный: при отсутствии переменная не задаётся, сервер стартует.
- `--dir ENV=~/path` — раскрыть `~`, создать каталог, положить абсолютный путь в `ENV`.
- `headers` — напечатать JSON-объект заголовков для `headersHelper`.
- `check` — для каждого известного секрета показать источник (env / keyring / не найден) и
  сделать живой запрос к сервису (код ответа). Значения не выводятся.

Поиск секрета `name`: переменная `QAILY_<NAME в верхнем регистре>` → `keyring.get_password("qaily", name)`.
Значение обрезается `strip()`. Ошибка бэкенда `keyring` (`NoKeyringError` и т.п.) — промах,
не падение.

Запуск сервера: POSIX — `os.execvpe` (без лишнего процесса, сигналы напрямую); Windows —
`subprocess.run` с унаследованным stdio и проброшенным кодом выхода (`os.exec*` на Windows
порождает новый процесс и завершает родителя, что рвёт stdio-канал MCP).

Имена секретов: `allure`, `redmine`, `kaiten` (обязательные),
`context7` (необязательный). Сервис в `keyring` — `qaily`. Имена короткие намеренно:
Claude Code вырезает из окружения `headersHelper` переменные с суффиксами `_TOKEN`, `_KEY`,
`_SECRET`, `_PASSWORD` (проверено на 2.1.294), поэтому `QAILY_ALLURE_TOKEN` до хелпера
`testops` не дошёл бы, а `QAILY_ALLURE` доходит.

### `mcp-servers.json`

| Сервер | Было | Станет |
|---|---|---|
| `testops` | `headers.Authorization` с `${user_config.allure}` | `headersHelper`: `uv run --script ${CLAUDE_PLUGIN_ROOT}/bin/qaily_launch.py headers "Authorization=Api-Token {allure}"` |
| `redmine` | `uvx …` + `${user_config.redmine}`, `/tmp/qaily-redmine` | `uv run --script … run --secret REDMINE_API_KEY=redmine --dir REDMINE_ALLOWED_DIRECTORIES=~/.qaily/redmine -- uvx --from mcp-redmine==… mcp-redmine` |
| `kaiten` | `uvx …` + `${user_config.kaiten}` | `… run --secret KAITEN_TOKEN=kaiten -- uvx --from git+…@… kaiten-mcp` |
| `context7` | `npx …` + `${user_config.context7}` | `… run --secret CONTEXT7_API_KEY=context7? -- npx -y @upstash/context7-mcp@…` |
| `playwright`, `chrome-devtools`, `jam` | — | без изменений |

Версии и пины серверов (`…` в таблице) — текущие из `mcp-servers.json`, не меняются.
Несекретные `env` (`REDMINE_URL`, `REDMINE_READ_ONLY`, `KAITEN_BASE_URL`, `KAITEN_MCP_MODULES`)
остаются в `env` сервера. Имена серверов не меняются — инструменты остаются
`mcp__plugin_qaily_<server>__*`, агенты и маски разрешений не ломаются.

Запасной путь для `testops`, если `headersHelper` у плагинного сервера в Desktop не работает:
stdio-прокси `… run --secret QAILY_AUTH=allure -- npx -y mcp-remote@<pin> <url> --header "Authorization:Api-Token ${QAILY_AUTH}"`
(точная форма передачи заголовка — по документации `mcp-remote` на этапе 0).

### Каталог вложений Redmine

`~/.qaily/redmine` вместо `/tmp/qaily-redmine`. `mcp-redmine` прогоняет `save_path` через
`expanduser()` и возвращает абсолютный `saved_to`; `REDMINE_ALLOWED_DIRECTORIES` тильду не
раскрывает — абсолютный путь подставляет лаунчер (`--dir`). Проверено на закэшированной версии
`mcp-redmine`; на зафиксированной `2026.09.10.084818` перепроверить на этапе 0.

- Агенты: `save_path: "~/.qaily/redmine/<id задачи>/<attachment_id>-<filename>"`, файл читать
  по `saved_to` из ответа.
- `settings.local.json.example`: `Read(~/.qaily/redmine/**)` вместо `Read(//tmp/…)` и
  `Read(//private/tmp/…)`.

### `plugin.json`

Блок `userConfig` удаляется. Версия `0.4.0`.

### Скилл `/qaily:doctor`

Запускает `uv run --script ${CLAUDE_PLUGIN_ROOT}/bin/qaily_launch.py check` и пересказывает
результат: какие токены найдены и где, какие сервисы ответили `200`/`401`, что сделать для
каждого промаха. Работает одинаково в Desktop и CLI на любой ОС, пользователю не нужен путь
к кэшу плагина.

## Обработка ошибок

| Ситуация | Поведение |
|---|---|
| Обязательный секрет не найден | Код 1, stderr: `qaily: не найден токен <name>. Задайте: uvx keyring set qaily <name> (или переменную QAILY_<NAME>)` |
| Нет бэкенда `keyring` | Промах; в сообщении совет задать `QAILY_*` |
| Необязательный секрет не найден | Сервер стартует без переменной, без сообщения |
| `headers` без секрета | stdout пуст, код ≠ 0, текст в stderr |
| Пробелы/перевод строки в токене | `strip()` |

Значения секретов не попадают ни в stdout, ни в stderr ни при каких ошибках.

Риски, проверяемые на этапе 0:

1. **Диалог Keychain на macOS.** Запись делает `uvx keyring`, чтение — `uv run --script`;
   при разных интерпретаторах macOS спросит доступ (в Desktop — GUI-диалог, ответ «Всегда
   разрешать»), диалог может повториться после обновления Python в `uv`. При подтверждении —
   описать в README.
2. **Первый запуск `uv run --script`** качает `keyring` (и, возможно, Python) и может не
   уложиться в таймаут запуска MCP. Смягчение: `uvx keyring set` при онбординге прогревает
   общий кэш `uv`.
3. **`headersHelper` в Desktop** — при неработоспособности запасной путь `mcp-remote`.

## Онбординг, миграция, README

Пререквизиты по ОС:

| | macOS | Windows | Linux |
|---|---|---|---|
| Node 20+ | `brew install node` | `winget install OpenJS.NodeJS.LTS` | пакетный менеджер / nodejs.org |
| uv | `brew install uv` | `winget install astral-sh.uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| git | Xcode CLT / brew | Git for Windows (нужен Claude Code) | пакетный менеджер |

Установка: CLI — `/plugin marketplace add …`, `/plugin install qaily@qaily`; Desktop — «+» →
Plugins → Add plugin. Токены — одинаково на всех ОС, ввод скрыт:

```
uvx keyring set qaily allure
uvx keyring set qaily redmine
uvx keyring set qaily kaiten
uvx keyring set qaily context7   # необязательно
```

Linux без Secret Service (сервер, WSL, контейнер) — переменные `QAILY_*` в `~/.profile`.
Затем перезапуск сессии и `/qaily:doctor`.

Миграция 0.3.x → 0.4.0: обновить плагин, три команды `keyring set`, `/qaily:doctor`. Старые
значения `userConfig` остаются в хранилище Claude Code неиспользуемыми.

`GITLAB_TOKEN` (MR-режим `review-autotest`) остаётся переменной окружения: его читает `curl`
в Bash-инструменте, который загружает профиль shell (в т.ч. в Desktop; на Windows — Git Bash).
Через лаунчер не пропускаем: печать секрета попала бы в транскрипт. README: `export` для
bash/zsh и `setx GITLAB_TOKEN …` для Windows.

Прочие правки README: раздел «Проверка токенов вручную» (`curl` с `$VAR`) заменяется на
`/qaily:doctor`; в «Если что-то не работает» — диалог Keychain, Linux без Secret Service,
медленный первый запуск `uv`; строка про системный keychain — для всех трёх ОС; пометка, что
Desktop есть на macOS и Windows.

## Проверка

**Этап 0 — проверка на Mac (до остальных работ).** CLI: `claude --plugin-dir <ветка> mcp list` —
`redmine`, `kaiten`, `context7` поднимаются через лаунчер, `testops` — через `headersHelper`.
Desktop: новая сессия пользователя, проверка списка инструментов и диалога Keychain. При
неработающем `headersHelper` — сразу переход `testops` на `mcp-remote`.

**Этап 1 — тест лаунчера** `bin/test_qaily_launch.py` (`uv run --with pytest`), бэкенд
`keyring` подменён, реальных секретов нет:

- `QAILY_*` приоритетнее `keyring`; промах в обоих — код 1 и сообщение с командой;
- `?` — необязательный секрет не мешает старту;
- `--dir` — `~` раскрыт, каталог создан, путь абсолютный;
- `headers` — шаблон подставлен, вывод — валидный JSON;
- значение секрета не встречается в stdout/stderr при ошибках;
- ветка запуска: `subprocess` на Windows, `exec` на POSIX (через подмену `sys.platform`).

**Этап 2 — Linux в Docker** (CLI, без Secret Service — путь `QAILY_*`): контейнер с uv, Node,
Claude Code; `qaily_launch.py check` и `claude mcp list`. Токены передаёт пользователь
(`docker run -e QAILY_…`). Linux с Secret Service не проверяется отдельно.

**Этап 3 — Windows-VM, ручной прогон по чек-листу** (таблица «шаг → ожидаемое → факт»):

1. установка пререквизитов по README (winget, Git for Windows);
2. установка плагина в CLI и Desktop;
3. `uvx keyring set` ×3, `/qaily:doctor` — все токены найдены, `200`;
4. все 7 серверов подключены в CLI и Desktop (`jam` — после OAuth);
5. по сценарию на скилл: `test-design`, `review-testcase`, `review-autotest` (одиночный и MR
   с `setx GITLAB_TOKEN`), `launch-triage`, `coverage-gap-design`;
6. вложение Redmine скачивается в `~/.qaily/redmine` и читается агентом.

По найденному — правки и повторный прогон упавших шагов.

**Этап 4 — регресс на macOS:** сокращённый чек-лист в CLI и Desktop, проверка миграции с 0.3.x.

## Критерии готовности

- 7 серверов подключены: Desktop и CLI на macOS и Windows, CLI на Linux.
- 5 скиллов и `/qaily:doctor` проходят сценарий на Windows.
- Значения секретов не встречаются в логах и выводе.

## Вне объёма

- CI на GitHub Actions.
- Отдельная проверка Linux с Secret Service.
- Удаление старых значений `userConfig` из хранилища Claude Code.
