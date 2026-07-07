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
