# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин со скиллами тест-дизайна, ревью тест-кейсов и ревью автотестов, MCP-интеграциями (Allure TestOps, Redmine, Kaiten — карточки и документы/wiki, Jam — записи багов с логами и сетью) плюс браузерная автоматизация (Playwright, Chrome DevTools) для прогона и отладки UI-сценариев.

## Установка

Пререквизиты (один раз):

1. Claude Code ≥ 2.1.154: `claude --version`; обновить — `claude update`.
2. Node.js 20+: `brew install node` или [nodejs.org](https://nodejs.org).
3. uv (для Redmine и Kaiten MCP): `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. git (Kaiten MCP ставится uvx-ом из git-репозитория)
5. Chrome/Chromium (для Playwright и Chrome DevTools MCP). Playwright ставит браузер сам: `npx playwright install chromium`. Первый запуск браузерных серверов медленный — npx качает пакеты и браузер.

Установка плагина — две команды в Claude Code:

```
/plugin marketplace add <git-url-репозитория>
/plugin install qaily@qaily
```

При включении Claude Code сам спросит токены (хранятся в системном keychain):

| Поле | Где взять |
|------|-----------|
| Allure TestOps API token | Allure TestOps → профиль → API tokens |
| Redmine API key | Redmine → Моя учётная запись → Ключ API. **Строго read-only ключ** |
| Kaiten API token | Kaiten → профиль → API-ключ |

Jam токена не просит — авторизация по OAuth: после установки выполнить `/mcp` → `jam` → войти в браузере. Без этого инструменты Jam недоступны.

Проверка: в сессии спросить «покажи тест-кейсы проекта 35 из Allure».

Доступ к репозиторию — по git (ssh-ключ или токен), как для обычного clone.

## Проверка токенов вручную

```sh
curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "https://astbroker.qatools.cloud/api/rs/project" | head -c 200
curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "https://redmine.fast-system.ru/users/current.json"
curl -s -H "Authorization: Bearer $KAITEN_API_TOKEN" "https://lab-company.kaiten.ru/api/latest/users/current"
```

`401` — токен неверный.

## Если что-то не работает

- `/plugin` → qaily → статус компонентов; `claude mcp list` — статус серверов.
- Типовые причины: старый Claude Code, нет Node.js / uv / git, неверный токен (см. curl-проверки выше).
- Первый старт Kaiten-сервера медленный: uvx клонирует и собирает пакет из git (дальше — из кэша).
- Jam в статусе «needs authentication» — пройти OAuth через `/mcp` (только в интерактивной сессии).
- Обновление плагина: `/plugin marketplace update qaily`.

## MCP-сервер ТестОпс (`testops`)

Официальный MCP ТестОпс — HTTP-эндпоинт `https://astbroker.qatools.cloud/api/mcp`, авторизация
API-токеном (`Authorization: Api-Token <токен>`). Локально ничего не ставится, Node.js для него
не нужен. Инструменты с префиксом `testops_` (30 штук): поиск и правка кейсов, папок, общих
шагов, дефектов, запусков. Поиск — AQL-запросами (`testops_find_testcases` с `aql` и `expand`),
отдельных ручек вида `get_test_case_overview` / `get_test_case_steps` больше нет: всё, что нужно
для ревью, отдаёт один вызов с `expand: ["all"]`.
Документация: https://docs.qatools.ru/ecosystem/mcp/setup

Свой форк опенсорсного сервера (`vendor/allure-testops-mcp.mjs`) удалён — скиллы и суб-агент
`doc-researcher` переведены на `testops_*`.

### Запись разрешена, но с подтверждением

Режима read-only у официального сервера нет: 19 мутирующих инструментов публикуются всегда.
Контроль записи — ask-правила из шаблона [settings.local.json.example](settings.local.json.example):
каждое создание, изменение и удаление Claude обязан подтвердить у пользователя. Скопируйте
шаблон в рабочий проект (см. раздел ниже), иначе гарантии запроса нет.

Под правила попадают `testops_create_*`, `testops_update_*`, `testops_delete_*`,
`testops_restore_*`, `testops_add_*`, `testops_link_*`, `testops_run_*`, `testops_mark_*`,
`testops_unmark_*`. Чтение (`testops_find_*`, `testops_get_*`) не спрашивает.

⚠️ `ask` не работает в режиме `bypassPermissions` (`--dangerously-skip-permissions`) — в нём
запись пойдёт без вопросов.

## Ограничение записи в Kaiten (deny-маски)

Скопировать шаблон в свой рабочий проект (тот каталог, где запускается claude):

```sh
mkdir -p .claude && cp <путь-к-этому-репо>/settings.local.json.example .claude/settings.local.json
```

Маски запрещают мутирующие инструменты Kaiten и требуют подтверждения на запись в TestOps. `allow`-правила разрешают без вопросов скачивание и чтение вложений Redmine и чтение файлов плагина.

Шаблон уже копировали до версии 0.3.2 → скопируйте заново или перенесите блок `allow` вручную, иначе чтение вложений Redmine будет спрашивать доступ.

Маски привязаны к именам инструментов плагина (`mcp__plugin_qaily_...`).
Если поднимать серверы НЕ через плагин (старый способ, project-scope .mcp.json) —
эти маски их не покроют.

**Браузерные MCP (Playwright, Chrome DevTools) намеренно НЕ ограничены** — клик, ввод,
навигация им нужны для прогона E2E, это их работа. Масками не режем. Граница безопасности
тут не «read-only», а выбор стенда: наводить их только на тестовые окружения, не на боевой UI.

## Ревью автотестов (скилл review-autotest)

Скилл сопоставляет три источника — требования Redmine-задачи, ручной тест-кейс Allure TestOps и код автотеста (pytest + allure-pytest) — и даёт ревью с конкретными правками по 4 блокам критериев (соответствие кейсу, покрытие требований, качество кода, метаданные/связность). Ревью read-only: код, кейсы и задачи не меняются. Связка кейс ↔ код — через декоратор `@allure.id("<id>")` в тесте.

Запускается из каталога репозитория автотестов (текущий cwd сессии). Режим определяется по входу:

| Режим | Вход | Пример запроса |
|-------|------|-----------------|
| Одиночный | TestOps-кейс | «ревью автотеста для кейса 39979» |
| Пачечный | Redmine-задача | «ревью автотестов по задаче #1234» |
| MR (diff) | GitLab merge request | «ревью автотестов в MR \<url\>» |

Одиночный режим даёт отчёт по блокам; пачечный и MR — сводную таблицу по кейсам/тестам плюс детали по проблемным.

Во всех трёх режимах кейс ревьюит суб-агент `autotest-reviewer` (`agents/autotest-reviewer.md`, read-only): алгоритм ревью одного кейса и блоки критериев описаны там, скилл занимается только режимами, сбором входных данных и сводкой. Агент читает свой промпт сам — скилл передаёт ему данные (`case_id`, требования, cwd, формат ответа), а не шаги.

Для MR-режима: если ветка MR уже есть локально, ревью идёт через `git diff` — токен не нужен. Для ревью MR по одной ссылке без локальной ветки нужен доступ к GitLab API:

```sh
export GITLAB_TOKEN=<token>   # scope read_api, строго read-only
```

Токен намеренно **не** добавлен в `userConfig` плагина: `userConfig` пробрасывается только в MCP-серверы, а GitLab-токен скилл читает из переменной окружения напрямую (curl / `glab mr diff`).

## Разбор упавших прогонов (скилл launch-triage)

Скилл берёт ID запуска Allure TestOps, группирует падения по корневой причине (текст ошибки → нормализованная сигнатура) и отдаёт сводку в чат: сколько падений, какие группы, какого типа каждая и что чинить. Контекст задачи подтягивается автоматически: номер Redmine берётся из привязанной к запуску задачи, а если её нет — из имени релиза (у нас имя релиза = номер задачи). Разбор read-only: ни кейсы, ни дефекты, ни задачи не меняются.

Чтение результатов делегируется суб-агенту `failure-analyst` — результаты TestOps приходят вместе со стеками, и в главном треде их держать нельзя.

| Вход | Пример запроса |
|------|-----------------|
| ID запуска | «разбери прогон 4498» |
| Ссылка на запуск | «почему упал <https://astbroker.qatools.cloud/launch/5034>» |

Прогон в другом проекте — скилл спросит `projectId`.

## Проекты для обкатки (фаза 0)

| Система | Проект | ID | Режим |
|---------|--------|----|-------|
| Allure TestOps | https://astbroker.qatools.cloud/project/35 | 35 | запись разрешена, каждая операция — с подтверждением пользователя (ask-правила) |
| Redmine | https://redmine.fast-system.ru/projects/pfpa (Fast-system) | 1 (`pfpa`) | **боевой**, строго read-only |

Redmine — боевой проект: только чтение задач, никакой записи.

Read-only для Redmine держится **правами токена на стороне Redmine** — отдельный аккаунт/роль строго на просмотр. Это физическая защита: MCP-сервер `mcp-redmine` даёт обобщённый инструмент `redmine_request` (path + method), поэтому deny-маски Claude по имени инструмента запись отсечь не могут — GET и DELETE идут через один и тот же тул. С read-only ключом запрос на запись вернёт 403 независимо от конфига Claude. Вторая линия — `REDMINE_READ_ONLY=1` в `mcp-servers.json`: сервер сам отклоняет любой не-GET запрос, включая `redmine_upload`.

Вложения задач скилл и агенты скачивают через `redmine_download` в `/tmp/qaily-redmine` (`REDMINE_ALLOWED_DIRECTORIES` в `mcp-servers.json`), картинки смотрят через `redmine_attachment_image`. Чтение скачанных файлов разрешено `allow`-правилами шаблона [settings.local.json.example](settings.local.json.example) — без них каждый агент спросит доступ к `/tmp`.

> При смене Redmine-ключа на пишущий пропадает первая линия защиты, остаётся только `REDMINE_READ_ONLY` — держим read-only роль осознанно.

Deny-правила в `settings.local.json` (фаза 1.3) остаются для **Kaiten** — его мутирующие инструменты ограничиваются масками по именам. Для TestOps запись не запрещена, а поставлена на подтверждение — ask-правила в том же шаблоне. Полный список мутирующих инструментов Kaiten — в шаблоне [settings.local.json.example](settings.local.json.example).

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._
