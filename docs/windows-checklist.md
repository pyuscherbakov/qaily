# Чек-лист прогона qaily на Windows

Ветка `feat/cross-platform`, qaily 0.4.0. Заполнять колонку «Факт»; при расхождении — текст ошибки
или скриншот. Шаги 4–6 повторяются отдельно для **CLI** и **Desktop**.

## 1. Установка

| № | Шаг | Ожидаемое | Факт | ОК |
|---|---|---|---|---|
| 1.1 | Git for Windows, затем `winget install OpenJS.NodeJS.LTS` и `winget install astral-sh.uv`; открыть новый терминал | `git --version`, `node --version` (≥ 20), `uv --version` отвечают | | |
| 1.2 | Установить Claude Code и Claude Desktop, `claude --version` | ≥ 2.1.294 | | |
| 1.3 | CLI: `/plugin marketplace add <git-url>`, переключить marketplace на ветку `feat/cross-platform`, `/plugin install qaily@qaily` | плагин установлен, токены **не** спрашиваются | | |
| 1.4 | Desktop: «+» → Plugins → Add plugin → qaily | плагин включён | | |

## 2. Токены

| № | Шаг | Ожидаемое | Факт | ОК |
|---|---|---|---|---|
| 2.1 | PowerShell: `uvx keyring set qaily allure`, `… redmine`, `… kaiten` | ввод скрыт, ошибок нет | | |
| 2.2 | «Диспетчер учётных данных» → «Учётные данные Windows» | есть записи `allure@qaily`, `redmine@qaily` и `qaily` (пользователь `kaiten`) — keyring хранит последний секрет под голым именем сервиса | | |

## 3. Диагностика

| № | Шаг | Ожидаемое | Факт | ОК |
|---|---|---|---|---|
| 3.1 | Новая сессия, `/qaily:doctor` | `allure`, `redmine`, `kaiten`: `keyring — HTTP 200`; `context7`: «не найден (необязательный)» | | |
| 3.2 | `setx QAILY_CONTEXT7 test`, перезапуск Claude Desktop; для CLI — **новое** окно терминала; `/qaily:doctor` | `context7: env`, вывод без «кракозябр» | | |
| 3.3 | PowerShell: `[Environment]::SetEnvironmentVariable('QAILY_CONTEXT7',$null,'User')`, перезапуск как в 3.2 | `context7: не найден (необязательный)` | | |

## 4. MCP-серверы (CLI и Desktop)

| № | Шаг | Ожидаемое | CLI | Desktop |
|---|---|---|---|---|
| 4.1 | **Самая первая** сессия после установки: CLI — `claude mcp list`; Desktop — «перечисли доступные MCP-серверы qaily» | `testops`, `redmine`, `kaiten`, `context7`, `playwright`, `chrome-devtools` — подключены; если `testops` не подключился (холодный старт uv > 10 с) — записать и повторить в новой сессии | | |
| 4.2 | «покажи тест-кейсы проекта 35 из Allure» | список кейсов (`testops` + `headersHelper` с путём `C:\Users\…`) | | |
| 4.3 | «открой example.com в браузере и сделай снимок» | `playwright` открыл страницу | | |
| 4.4 | «через chrome-devtools открой example.com, покажи заголовок» | заголовок `Example Domain` | | |
| 4.5 | `/mcp` → `jam` → вход в браузере | `jam` подключён | | |

## 5. Скиллы (CLI и Desktop)

| № | Скилл | Сценарий | Ожидаемое | CLI | Desktop |
|---|---|---|---|---|---|
| 5.1 | `test-design` | «сгенерируй тест-кейсы по задаче #<id>» (задача с PDF-вложением) | кейсы предложены, вложение прочитано | | |
| 5.2 | `review-testcase` | «ревью тест-кейса <ссылка>» | ревью по 17 пунктам | | |
| 5.3 | `review-autotest` | одиночный: «ревью автотеста для кейса <ссылка>» из каталога репо автотестов | отчёт по 4 блокам | | |
| 5.4 | `review-autotest` | MR: `setx GITLAB_TOKEN <token>`, перезапуск, «ревью автотестов в MR <url>» | diff получен через API, сводная таблица | | |
| 5.5 | `launch-triage` | «разбери прогон <ссылка на launch>» | группы падений с причинами | | |
| 5.6 | `coverage-gap-design` | «покрой API по спеке <url openapi>» | список непокрытых операций | | |

## 6. Вложения Redmine и процессы

| № | Шаг | Ожидаемое | CLI | Desktop |
|---|---|---|---|---|
| 6.1 | После 5.1: `dir %USERPROFILE%\.qaily\redmine\<id>` | файл вложения на месте | | |
| 6.2 | Закрыть сессию Claude, «Диспетчер задач» через 10 с | нет оставшихся `node.exe` / `python.exe` / `uv.exe` / `chrome.exe` от qaily | | |
| 6.3 | Новая сессия, повторить 4.3 | `playwright` открыл страницу (нет «browser already in use») | | |
| 6.4 | После 5.1 (Read вложения) | Claude не спрашивал разрешение на чтение `~/.qaily/redmine` (при наличии `settings.local.json` из шаблона) | | |
