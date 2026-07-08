# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин с субагентами, скиллами и MCP-интеграциями (Redmine, Allure TestOps, Kaiten).

Скоуп первой версии — тест-дизайн: генерация кейсов, тест-планы, регрессия. Автотесты — позже.

План работ: [PLAN.md](PLAN.md).

## Настройка токенов

Токены — только в личных env-переменных, в репозиторий не коммитить:

```sh
export ALLURE_ENDPOINT="https://astbroker.qatools.cloud"
export ALLURE_TOKEN="<user token>"      # Allure TestOps → профиль → API tokens
export REDMINE_URL="https://redmine.fast-system.ru"
export REDMINE_API_KEY="<read-only ключ>" # ключ аккаунта/роли строго на просмотр; Redmine → Моя учётная запись → Ключ API
export KAITEN_API_URL="https://lab-company.kaiten.ru/api/latest" # базовый URL уже с /api/latest
export KAITEN_API_TOKEN="<api key>"     # Kaiten → профиль → API-ключ
```

Проверка токенов:

```sh
curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "$ALLURE_ENDPOINT/api/rs/project" | head -c 200
curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "$REDMINE_URL/users/current.json"
curl -s -H "Authorization: Bearer $KAITEN_API_TOKEN" "$KAITEN_API_URL/users/current"
```

## Установка Allure TestOps MCP

Конфигурация уже в репозитории — [.mcp.json](.mcp.json). Сервер [allure-testops-mcp](https://github.com/pyuscherbakov/allure-testops-mcp) (наш форк [armanayvazyan/allure-testops-mcp](https://github.com/armanayvazyan/allure-testops-mcp) с режимом `ALLURE_READ_ONLY`) лежит в репозитории готовым бандлом — [vendor/allure-testops-mcp.mjs](vendor/allure-testops-mcp.mjs); ни git, ни установка пакетов, ни сборка не нужны. Исходный коммит и инструкция пересборки — в [vendor/README.md](vendor/README.md).

Шаги для пользователя:

1. Установить Node.js 20+: `brew install node` или [nodejs.org](https://nodejs.org).

2. Получить личный API-токен: Allure TestOps → профиль → API tokens.

3. Прописать env-переменные в shell-профиле (`~/.zshrc`):

   ```sh
   export ALLURE_ENDPOINT="https://astbroker.qatools.cloud"
   export ALLURE_TOKEN="<user token>"
   ```

4. Проверить токен:

   ```sh
   curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "$ALLURE_ENDPOINT/api/rs/project" | head -c 200
   ```

   Ответ — JSON со списком проектов. `401` — токен неверный.

5. Запустить Claude Code в каталоге проекта. На вопрос про MCP-серверы из `.mcp.json` ответить «approve».

Проверка: в сессии спросить «покажи тест-кейсы проекта 35 из Allure» — Claude должен прочитать их через `list_test_cases`.

Проект по умолчанию — 35 (тестовый, `ALLURE_PROJECT_ID` в `.mcp.json`); другой проект указывается в запросе явно (`projectId`/`projectName`).

Если сервер не появился: `claude mcp list` покажет статус; типовые причины — нет Node.js, не экспортированы переменные, не выдан approve (сбросить: `claude mcp reset-project-choices`).

Запись в Allure ограничивается deny-масками из [settings.local.json.example](settings.local.json.example) — они покрывают все мутирующие инструменты текущей версии сервера: `create_*`, `update_*`, `delete_*`, `set_*`, `add_*`, `remove_*`, `bulk_*` плюс поимённые (`restore_test_case`, `rename_custom_field_value`, `merge_custom_field_values`, `close_launch`, `reopen_launch`, `run_test_plan`, `resolve_test_result`, `assign_test_result`). Маски привязаны к именам инструментов, поэтому при обновлении сервера новый мутирующий инструмент может пройти мимо списка. Жёсткая гарантия только чтения — `ALLURE_READ_ONLY=true` в env сервера: мутирующие инструменты исчезают из реестра целиком. Для сценария тест-дизайна (генерация кейсов в тестовый проект 35) read-only не включаем — запись нужна; соответствующие deny-строки тогда убираются из локального `settings.local.json`.

## Установка Redmine MCP

Конфигурация уже в репозитории — [.mcp.json](.mcp.json) подхватывается Claude Code автоматически. Сервер [mcp-redmine](https://github.com/runekaagaard/mcp-redmine) ставится с PyPI при первом запуске, отдельная установка не нужна.

Шаги для пользователя:

1. Установить [uv](https://docs.astral.sh/uv/getting-started/installation/) (сервер запускается через `uvx`):

   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Получить личный API-ключ: Redmine → Моя учётная запись → Ключ API. Ключ должен быть от аккаунта/роли **строго на просмотр** (см. раздел про read-only ниже).

3. Прописать env-переменные в shell-профиле (`~/.zshrc`):

   ```sh
   export REDMINE_URL="https://redmine.fast-system.ru"
   export REDMINE_API_KEY="<read-only ключ>"
   ```

4. Проверить ключ:

   ```sh
   curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "$REDMINE_URL/users/current.json"
   ```

   Ответ — JSON с вашим пользователем. `401` — ключ неверный.

5. Запустить Claude Code в каталоге проекта. На вопрос про MCP-серверы из `.mcp.json` ответить «approve».

Проверка: в сессии спросить «покажи задачу №<id> из Redmine» — Claude должен прочитать её через инструмент `redmine_request`.

Если сервер не появился: `claude mcp list` покажет статус; типовые причины — не установлен `uv`, не экспортированы переменные, не выдан approve (сбросить: `claude mcp reset-project-choices`).

## Установка Kaiten MCP

Конфигурация уже в репозитории — [.mcp.json](.mcp.json). Сервер [kaiten-mcp-server](https://github.com/pyuscherbakov/kaiten-mcp-server) (наш форк [vsaranyuk/kaiten-mcp-server](https://github.com/vsaranyuk/kaiten-mcp-server)) лежит в репозитории готовым бандлом — [vendor/kaiten-mcp-server.mjs](vendor/kaiten-mcp-server.mjs); ни git, ни установка пакетов, ни сборка не нужны. Исходный коммит и инструкция пересборки — в [vendor/README.md](vendor/README.md).

Шаги для пользователя:

1. Установить Node.js 20+: `brew install node` или [nodejs.org](https://nodejs.org).

2. Получить личный API-токен: Kaiten → профиль → API-ключ.

3. Прописать env-переменные в shell-профиле (`~/.zshrc`):

   ```sh
   export KAITEN_API_URL="https://lab-company.kaiten.ru/api/latest"  # базовый URL уже с /api/latest
   export KAITEN_API_TOKEN="<api key>"
   ```

   Пространство по умолчанию (`KAITEN_DEFAULT_SPACE_ID`) в общий `.mcp.json` не вынесено — оно опционально и индивидуально. Кому нужно, задаёт его в личном user-scope: `claude mcp add kaiten -s user -e KAITEN_DEFAULT_SPACE_ID=<id> ...`, либо указывает пространство в запросе явно.

4. Проверить токен:

   ```sh
   curl -s -H "Authorization: Bearer $KAITEN_API_TOKEN" "$KAITEN_API_URL/users/current"
   ```

   Ответ — JSON с вашим пользователем. `401` — токен неверный.

5. Запустить Claude Code в каталоге проекта. На вопрос про MCP-серверы из `.mcp.json` ответить «approve».

Проверка: в сессии спросить «покажи мои карточки из Kaiten» — Claude должен прочитать их через инструменты `kaiten_*` (например `kaiten_search_cards`).

Если сервер не появился: `claude mcp list` покажет статус; типовые причины — нет Node.js, не экспортированы переменные, не выдан approve (сбросить: `claude mcp reset-project-choices`).

Активировать deny-маски (один раз на проект — шаблон в git, локальный файл нет):

```sh
mkdir -p .claude && cp settings.local.json.example .claude/settings.local.json
```

Запись в Kaiten ограничивается этими deny-масками (из [settings.local.json.example](settings.local.json.example)) — они покрывают мутирующие инструменты по префиксам `kaiten_create_*`, `kaiten_update_*`, `kaiten_delete_*`. Маски привязаны к именам инструментов; у kaiten-сервера **нет** отдельного env-флага «только чтение» (в отличие от Allure `ALLURE_READ_ONLY`), поэтому жёсткой гарантии на стороне сервера нет — при обновлении сервера новый мутирующий инструмент может пройти мимо списка. Для физической защиты используйте Kaiten API-токен с правами только на чтение.

## Проекты для обкатки (фаза 0)

| Система | Проект | ID | Режим |
|---------|--------|----|-------|
| Allure TestOps | https://astbroker.qatools.cloud/project/35 | 35 | тестовый, запись разрешена |
| Redmine | https://redmine.fast-system.ru/projects/pfpa (Fast-system) | 1 (`pfpa`) | **боевой**, строго read-only |

Redmine — боевой проект: только чтение задач, никакой записи.

Read-only для Redmine держится **правами токена на стороне Redmine** — отдельный аккаунт/роль строго на просмотр. Это физическая защита: MCP-сервер `mcp-redmine` даёт единственный обобщённый инструмент `redmine_request` (path + method), поэтому deny-маски Claude по имени инструмента запись отсечь не могут — GET и DELETE идут через один и тот же тул. С read-only ключом запрос на запись вернёт 403 независимо от конфига Claude.

> При смене Redmine-ключа на пишущий эта защита пропадает — держим read-only роль осознанно.

Deny-правила в `settings.local.json` (фаза 1.3) остаются для **Allure и Kaiten** — у них по-инструментные тулы, маски по именам работают (полный список мутирующих инструментов Allure — в разделе про установку Allure MCP). Шаблон — [settings.local.json.example](settings.local.json.example).

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._
