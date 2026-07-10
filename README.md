# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин со скиллами тест-дизайна и ревью тест-кейсов и MCP-интеграциями (Allure TestOps, Redmine, Kaiten — карточки и документы/wiki) плюс браузерная автоматизация (Playwright, Chrome DevTools) для прогона и отладки UI-сценариев.

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

## Ограничение записи (deny-маски)

Скопировать шаблон в свой рабочий проект (тот каталог, где запускается claude):

```sh
mkdir -p .claude && cp <путь-к-этому-репо>/settings.local.json.example .claude/settings.local.json
```

Маски запрещают мутирующие инструменты Allure и Kaiten, установленные плагином.
Для сценария тест-дизайна (запись кейсов в тестовый проект 35) строки
`create_*` Allure из локального файла убираются.

Маски привязаны к именам инструментов плагина (`mcp__plugin_qaily_...`).
Если поднимать серверы НЕ через плагин (старый способ, project-scope .mcp.json) —
эти маски их не покроют.

**Браузерные MCP (Playwright, Chrome DevTools) намеренно НЕ ограничены** — клик, ввод,
навигация им нужны для прогона E2E, это их работа. Масками не режем. Граница безопасности
тут не «read-only», а выбор стенда: наводить их только на тестовые окружения, не на боевой UI.

## Проекты для обкатки (фаза 0)

| Система | Проект | ID | Режим |
|---------|--------|----|-------|
| Allure TestOps | https://astbroker.qatools.cloud/project/35 | 35 | тестовый, запись разрешена |
| Redmine | https://redmine.fast-system.ru/projects/pfpa (Fast-system) | 1 (`pfpa`) | **боевой**, строго read-only |

Redmine — боевой проект: только чтение задач, никакой записи.

Read-only для Redmine держится **правами токена на стороне Redmine** — отдельный аккаунт/роль строго на просмотр. Это физическая защита: MCP-сервер `mcp-redmine` даёт единственный обобщённый инструмент `redmine_request` (path + method), поэтому deny-маски Claude по имени инструмента запись отсечь не могут — GET и DELETE идут через один и тот же тул. С read-only ключом запрос на запись вернёт 403 независимо от конфига Claude.

> При смене Redmine-ключа на пишущий эта защита пропадает — держим read-only роль осознанно.

Deny-правила в `settings.local.json` (фаза 1.3) остаются для **Allure и Kaiten** — у них по-инструментные тулы, маски по именам работают. Полный список мутирующих инструментов — в шаблоне [settings.local.json.example](settings.local.json.example).

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._

---

Пересборка vendor-бандлов MCP-серверов — [vendor/README.md](vendor/README.md).
