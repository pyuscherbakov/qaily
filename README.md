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
export KAITEN_URL="https://<kaiten-host>"
export KAITEN_TOKEN="<api key>"         # Kaiten → профиль → API-ключ
```

Проверка токенов:

```sh
curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "$ALLURE_ENDPOINT/api/rs/project" | head -c 200
curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "$REDMINE_URL/users/current.json"
curl -s -H "Authorization: Bearer $KAITEN_TOKEN" "$KAITEN_URL/api/latest/users/current"
```

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

## Проекты для обкатки (фаза 0)

| Система | Проект | ID | Режим |
|---------|--------|----|-------|
| Allure TestOps | https://astbroker.qatools.cloud/project/35 | 35 | тестовый, запись разрешена |
| Redmine | https://redmine.fast-system.ru/projects/pfpa (Fast-system) | 1 (`pfpa`) | **боевой**, строго read-only |

Redmine — боевой проект: только чтение задач, никакой записи.

Read-only для Redmine держится **правами токена на стороне Redmine** — отдельный аккаунт/роль строго на просмотр. Это физическая защита: MCP-сервер `mcp-redmine` даёт единственный обобщённый инструмент `redmine_request` (path + method), поэтому deny-маски Claude по имени инструмента запись отсечь не могут — GET и DELETE идут через один и тот же тул. С read-only ключом запрос на запись вернёт 403 независимо от конфига Claude.

> При смене Redmine-ключа на пишущий эта защита пропадает — держим read-only роль осознанно.

Deny-правила в `settings.local.json` (фаза 1.3) остаются для **Allure и Kaiten** — у них по-инструментные тулы `create_*`/`update_*`/`delete_*`, маски работают. Шаблон — [settings.local.json.example](settings.local.json.example).

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._
