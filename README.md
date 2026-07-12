# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин со скиллами тест-дизайна, ревью тест-кейсов и ревью автотестов, MCP-интеграциями (Allure TestOps, Redmine, Kaiten — карточки и документы/wiki) плюс браузерная автоматизация (Playwright, Chrome DevTools) для прогона и отладки UI-сценариев.

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
| Allure TestOps: read-only режим | Оставить включённым (значение по умолчанию) |
| Redmine API key | Redmine → Моя учётная запись → Ключ API. **Строго read-only ключ** |
| Kaiten API token | Kaiten → профиль → API-ключ |

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
- Обновление плагина: `/plugin marketplace update qaily`.

## Allure TestOps: read-only и временный write-профиль

Allure запускается в read-only режиме по умолчанию: сервер публикует только 26 инструментов чтения и не показывает 30 мутирующих инструментов. Это серверное ограничение, поэтому для Allure не нужно копировать deny-маски в каждый проект.

Если нужна разрешённая запись в тестовый проект 35, временно смените настройку плагина `pluginConfigs["qaily@qaily"].options.allure_read_only` на `false` в настройках того scope, где установлен плагин (например, `~/.claude/settings.json` для user scope). Затем перезапустите сессию или выполните `/reload-plugins`. Сразу после операции верните значение `true` и снова перезагрузите плагины.

## Ограничение записи в Kaiten (deny-маски)

Скопировать шаблон в свой рабочий проект (тот каталог, где запускается claude):

```sh
mkdir -p .claude && cp <путь-к-этому-репо>/settings.local.json.example .claude/settings.local.json
```

Маски запрещают мутирующие инструменты Kaiten, установленные плагином.

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

Для MR-режима: если ветка MR уже есть локально, ревью идёт через `git diff` — токен не нужен. Для ревью MR по одной ссылке без локальной ветки нужен доступ к GitLab API:

```sh
export GITLAB_TOKEN=<token>   # scope read_api, строго read-only
```

Токен намеренно **не** добавлен в `userConfig` плагина: `userConfig` пробрасывается только в MCP-серверы, а GitLab-токен скилл читает из переменной окружения напрямую (curl / `glab mr diff`).

## Проекты для обкатки (фаза 0)

| Система | Проект | ID | Режим |
|---------|--------|----|-------|
| Allure TestOps | https://astbroker.qatools.cloud/project/35 | 35 | read-only по умолчанию; запись — только через временный write-профиль |
| Redmine | https://redmine.fast-system.ru/projects/pfpa (Fast-system) | 1 (`pfpa`) | **боевой**, строго read-only |

Redmine — боевой проект: только чтение задач, никакой записи.

Read-only для Redmine держится **правами токена на стороне Redmine** — отдельный аккаунт/роль строго на просмотр. Это физическая защита: MCP-сервер `mcp-redmine` даёт единственный обобщённый инструмент `redmine_request` (path + method), поэтому deny-маски Claude по имени инструмента запись отсечь не могут — GET и DELETE идут через один и тот же тул. С read-only ключом запрос на запись вернёт 403 независимо от конфига Claude.

> При смене Redmine-ключа на пишущий эта защита пропадает — держим read-only роль осознанно.

Deny-правила в `settings.local.json` (фаза 1.3) остаются для **Kaiten** — его мутирующие инструменты ограничиваются масками по именам. Для Allure эта защита реализована на стороне MCP-сервера: read-only режим не публикует инструменты записи. Полный список мутирующих инструментов Kaiten — в шаблоне [settings.local.json.example](settings.local.json.example).

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._

---

Пересборка vendor-бандлов MCP-серверов — [vendor/README.md](vendor/README.md).
