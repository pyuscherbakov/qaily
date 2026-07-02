# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин с субагентами, скиллами и MCP-интеграциями (Redmine, Allure TestOps, Kaiten).

Скоуп первой версии — тест-дизайн: генерация кейсов, тест-планы, регрессия. Автотесты — позже.

План работ: [PLAN.md](PLAN.md).

## Настройка токенов

Токены — только в личных env-переменных, в репозиторий не коммитить:

```sh
export ALLURE_ENDPOINT="https://<allure-host>"
export ALLURE_TOKEN="<user token>"      # Allure TestOps → профиль → API tokens
export REDMINE_URL="https://<redmine-host>"
export REDMINE_API_KEY="<личный ключ>"  # Redmine → Моя учётная запись → Ключ API
export KAITEN_URL="https://<kaiten-host>"
export KAITEN_TOKEN="<api key>"         # Kaiten → профиль → API-ключ
```

Проверка токенов:

```sh
curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "$ALLURE_ENDPOINT/api/rs/project" | head -c 200
curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "$REDMINE_URL/users/current.json"
curl -s -H "Authorization: Bearer $KAITEN_TOKEN" "$KAITEN_URL/api/latest/users/current"
```

## Тестовые проекты (фаза 0)

Обкатка только на тестовых проектах, боевые данные не трогаем:

| Система | Проект | ID |
|---------|--------|----|
| Allure TestOps | _TBD_ | _TBD_ |
| Redmine | _TBD_ | _TBD_ |

## Пилотная группа

_TBD: 2–3 QA с установленным Claude Code и подпиской._
