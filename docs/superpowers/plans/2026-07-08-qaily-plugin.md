# Qaily Claude Code Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить репозиторий qaily в устанавливаемый Claude Code плагин (3 MCP-сервера + скилл тест-дизайна) с маркетплейсом в этом же репозитории; установка у пользователя — две команды, токены запрашиваются диалогом.

**Architecture:** Корень репозитория = плагин И маркетплейс одновременно (`.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` с `source: "./"`). MCP-конфиг переезжает из корневого `.mcp.json` в `mcp-servers.json`, подключаемый через манифест; пути к vendor-бандлам — через `${CLAUDE_PLUGIN_ROOT}`; токены — через `userConfig`/`${user_config.*}` (sensitive → keychain). Deny-маски остаются механизмом уровня пользователя (`settings.local.json.example`), но префиксы инструментов обновляются под плагинные имена.

**Tech Stack:** Claude Code plugin system (plugin.json, marketplace.json, userConfig), Node.js 20+ (vendor-бандлы esbuild), uvx/PyPI (mcp-redmine), git.

## Global Constraints

- Claude Code ≥ 2.1.154 у всех участников пилота (нужны `userConfig`, `displayName`; проверять `claude --version`).
- Node.js ≥ 20 и `uv` — пререквизиты пользователя, плагин их не ставит.
- Vendor-бандлы (`vendor/*.mjs`) не пересобираются в рамках этого плана — используются как есть.
- Все пути в манифестах — относительные, начинаются с `./`; внутри MCP-конфига — только `${CLAUDE_PLUGIN_ROOT}`.
- Commit-сообщения — на русском, без Co-Authored-By.
- Имя плагина и маркетплейса: `qaily`. Установка: `/plugin marketplace add <git-url>` → `/plugin install qaily@qaily`.
- Read-only для Redmine держится правами токена (боевой проект), для Allure/Kaiten — deny-масками пользователя; плагин это не ослабляет.

---

### Task 1: Манифест плагина `.claude-plugin/plugin.json`

**Files:**
- Create: `.claude-plugin/plugin.json`

**Interfaces:**
- Produces: манифест с ключами `userConfig` (`allure_token`, `redmine_api_key`, `kaiten_api_token`, `kaiten_default_space_id`), на которые Task 2 ссылается как `${user_config.<key>}`. Ключ `mcpServers` в манифест добавит Task 2.

- [ ] **Step 1: Создать манифест**

```json
{
  "name": "qaily",
  "displayName": "Qaily QA Assistant",
  "version": "0.1.0",
  "description": "QA AI-ассистент: тест-дизайн с интеграциями Allure TestOps, Redmine, Kaiten",
  "author": {
    "name": "Pavel Shcherbakov",
    "email": "pyuscherbakov@gmail.com"
  },
  "repository": "https://github.com/pyuscherbakov/qaily",
  "keywords": ["qa", "test-design", "allure", "redmine", "kaiten"],
  "userConfig": {
    "allure_token": {
      "type": "string",
      "title": "Allure TestOps API token",
      "description": "Allure TestOps → профиль → API tokens",
      "sensitive": true,
      "required": true
    },
    "redmine_api_key": {
      "type": "string",
      "title": "Redmine API key (read-only)",
      "description": "Redmine → Моя учётная запись → Ключ API. Строго read-only ключ!",
      "sensitive": true,
      "required": true
    },
    "kaiten_api_token": {
      "type": "string",
      "title": "Kaiten API token",
      "description": "Kaiten → профиль → API-ключ",
      "sensitive": true,
      "required": true
    },
    "kaiten_default_space_id": {
      "type": "string",
      "title": "Kaiten space ID (опционально)",
      "description": "ID пространства Kaiten по умолчанию; пусто — указывать в запросе",
      "required": false,
      "default": ""
    }
  }
}
```

- [ ] **Step 2: Проверить валидатором**

Run: `claude plugin validate . --strict`
Expected: `Validation passed` (или аналогичный успешный вывод) без ошибок и предупреждений.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "Манифест плагина qaily с userConfig для токенов"
```

---

### Task 2: Миграция MCP-конфига в плагин

**Files:**
- Create: `mcp-servers.json`
- Modify: `.claude-plugin/plugin.json` (добавить ключ `mcpServers`)
- Delete: `.mcp.json`

**Interfaces:**
- Consumes: ключи `userConfig` из Task 1 (`${user_config.allure_token}` и т.д.).
- Produces: три MCP-сервера `allure-testops`, `redmine`, `kaiten`, стартующие при включении плагина. Имена серверов используются в Task 4/5 для deny-масок.

- [ ] **Step 1: Создать `mcp-servers.json`**

Отличия от старого `.mcp.json`: пути через `${CLAUDE_PLUGIN_ROOT}`, токены через `${user_config.*}`, добавлен `KAITEN_DEFAULT_SPACE_ID`.

```json
{
  "mcpServers": {
    "allure-testops": {
      "type": "stdio",
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/vendor/allure-testops-mcp.mjs"],
      "env": {
        "ALLURE_TESTOPS_URL": "${ALLURE_ENDPOINT:-https://astbroker.qatools.cloud}",
        "ALLURE_TOKEN": "${user_config.allure_token}",
        "ALLURE_PROJECT_ID": "35"
      }
    },
    "redmine": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "mcp-redmine==2026.1.13.152335", "mcp-redmine"],
      "env": {
        "REDMINE_URL": "${REDMINE_URL:-https://redmine.fast-system.ru}",
        "REDMINE_API_KEY": "${user_config.redmine_api_key}"
      }
    },
    "kaiten": {
      "type": "stdio",
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/vendor/kaiten-mcp-server.mjs"],
      "env": {
        "KAITEN_API_URL": "${KAITEN_API_URL:-https://lab-company.kaiten.ru/api/latest}",
        "KAITEN_API_TOKEN": "${user_config.kaiten_api_token}",
        "KAITEN_DEFAULT_SPACE_ID": "${user_config.kaiten_default_space_id}"
      }
    }
  }
}
```

- [ ] **Step 2: Подключить в манифест и удалить старый файл**

В `.claude-plugin/plugin.json` добавить после `"keywords"`:

```json
  "mcpServers": "./mcp-servers.json",
```

Удалить корневой `.mcp.json` (иначе при работе из каталога репозитория серверы поднимутся дважды: как project-scope и как плагинные):

```bash
git rm .mcp.json
```

- [ ] **Step 3: Smoke-тест бандлов**

Бандлы должны отвечать JSON-ом на `initialize` (проверка из vendor/README.md):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | ALLURE_TESTOPS_URL=https://astbroker.qatools.cloud ALLURE_TOKEN=dummy ALLURE_PROJECT_ID=35 node vendor/allure-testops-mcp.mjs | head -c 200
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | KAITEN_API_URL=https://lab-company.kaiten.ru/api/latest KAITEN_API_TOKEN=dummy node vendor/kaiten-mcp-server.mjs | head -c 200
```

Expected: обе команды печатают JSON-RPC ответ с `"result"` (не stack trace).

- [ ] **Step 4: Проверить валидатором**

Run: `claude plugin validate . --strict`
Expected: успех, ошибок про `mcpServers` нет.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json mcp-servers.json
git commit -m "MCP-конфиг перенесён в плагин: CLAUDE_PLUGIN_ROOT и user_config для токенов"
```

---

### Task 3: Маркетплейс `.claude-plugin/marketplace.json`

**Files:**
- Create: `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: имя плагина `qaily` из Task 1.
- Produces: маркетплейс `qaily`; команда установки `/plugin install qaily@qaily` (используется в Task 4 и README).

- [ ] **Step 1: Создать файл маркетплейса**

`source: "./"` — плагин лежит в корне того же репозитория.

```json
{
  "name": "qaily",
  "owner": {
    "name": "Pavel Shcherbakov",
    "email": "pyuscherbakov@gmail.com"
  },
  "plugins": [
    {
      "name": "qaily",
      "source": "./",
      "description": "QA AI-ассистент: тест-дизайн с интеграциями Allure TestOps, Redmine, Kaiten"
    }
  ]
}
```

- [ ] **Step 2: Проверить валидатором**

Run: `claude plugin validate . --strict`
Expected: успех; маркетплейс распознан.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "Маркетплейс qaily в том же репозитории"
```

---

### Task 4: Локальная E2E-проверка установки

**Files:**
- (изменений нет — только проверка; фиксы, если найдутся, коммитятся отдельно с понятным сообщением)

**Interfaces:**
- Consumes: маркетплейс из Task 3, MCP-серверы из Task 2, реальные токены исполнителя.
- Produces: подтверждённые фактические имена MCP-инструментов плагина (формат `mcp__plugin_qaily_<server>__<tool>` или иной) — записать их, они нужны Task 5 для deny-масок.

- [ ] **Step 1: Добавить маркетплейс из локального каталога и установить плагин**

В интерактивной сессии Claude Code (из любого каталога, НЕ обязательно из репозитория):

```
/plugin marketplace add /Users/pavelshcherbakov/code/work/ast/qaily
/plugin install qaily@qaily
```

Expected: Claude Code показывает диалог настройки с четырьмя полями из `userConfig`; после ввода токенов плагин включается.

- [ ] **Step 2: Проверить, что MCP-серверы поднялись**

Run: `claude mcp list` (или `/mcp` в сессии)
Expected: `allure-testops`, `redmine`, `kaiten` в статусе connected, с пометкой источника-плагина.

- [ ] **Step 3: Зафиксировать фактические имена инструментов**

В сессии выполнить любой запрос, показывающий инструменты (например «покажи тест-кейсы проекта 35 из Allure»), либо посмотреть имена в `/mcp` → сервер → tools.
Expected: чтение из Allure работает (`list_test_cases` возвращает кейсы проекта 35). Записать точный префикс инструментов (ожидаемо `mcp__plugin_qaily_allure-testops__list_test_cases`; если формат другой — записать фактический, он нужен в Task 5).

- [ ] **Step 4: Проверить Redmine и Kaiten**

В сессии: «покажи задачу №1 из Redmine» и «покажи мои карточки из Kaiten».
Expected: оба запроса отвечают данными, не ошибкой авторизации.

- [ ] **Step 5: Проверить работу из чужого каталога**

Запустить `claude` в каталоге вне репозитория qaily (например `~/`), повторить запрос к Allure.
Expected: работает — плагин не привязан к каталогу репозитория.

---

### Task 5: Deny-маски под плагинные имена инструментов

**Files:**
- Modify: `settings.local.json.example`

**Interfaces:**
- Consumes: фактический префикс инструментов из Task 4 Step 3. Ниже используется ожидаемый `mcp__plugin_qaily_<server>__`; если Task 4 показал другой — подставить фактический во все строки.
- Produces: шаблон deny-масок, работающий при установке через плагин.

- [ ] **Step 1: Обновить маски в `settings.local.json.example`**

Полное новое содержимое файла (старые префиксы `mcp__allure-testops__*` / `mcp__kaiten__*` заменяются плагинными; если пользователь всё ещё поднимает серверы project-scope из клона — плагинные маски их не покроют, это фиксируется комментарием в README, Task 7):

```json
{
  "permissions": {
    "deny": [
      "mcp__plugin_qaily_allure-testops__create_*",
      "mcp__plugin_qaily_allure-testops__update_*",
      "mcp__plugin_qaily_allure-testops__delete_*",
      "mcp__plugin_qaily_allure-testops__set_*",
      "mcp__plugin_qaily_allure-testops__add_*",
      "mcp__plugin_qaily_allure-testops__remove_*",
      "mcp__plugin_qaily_allure-testops__bulk_*",
      "mcp__plugin_qaily_allure-testops__restore_test_case",
      "mcp__plugin_qaily_allure-testops__rename_custom_field_value",
      "mcp__plugin_qaily_allure-testops__merge_custom_field_values",
      "mcp__plugin_qaily_allure-testops__close_launch",
      "mcp__plugin_qaily_allure-testops__reopen_launch",
      "mcp__plugin_qaily_allure-testops__run_test_plan",
      "mcp__plugin_qaily_allure-testops__resolve_test_result",
      "mcp__plugin_qaily_allure-testops__assign_test_result",

      "mcp__plugin_qaily_kaiten__kaiten_create_*",
      "mcp__plugin_qaily_kaiten__kaiten_update_*",
      "mcp__plugin_qaily_kaiten__kaiten_delete_*"
    ]
  }
}
```

- [ ] **Step 2: Проверить, что маска реально блокирует**

В сессии с установленным плагином и скопированным в текущий проект `.claude/settings.local.json` попросить: «создай тестовый кейс с именем DENY-CHECK в проекте 35».
Expected: вызов `create_test_case` отклонён permission-правилом (Claude сообщает, что инструмент запрещён). Если не блокируется — префикс в масках неверный, вернуться к Task 4 Step 3.

- [ ] **Step 3: Commit**

```bash
git add settings.local.json.example
git commit -m "Deny-маски обновлены под плагинные имена MCP-инструментов"
```

---

### Task 6: Скилл тест-дизайна

**Files:**
- Create: `skills/test-design/SKILL.md`

**Interfaces:**
- Consumes: MCP-инструменты плагина (Allure: `list_test_cases`, `search_test_cases`, `create_test_case`, `get_test_case_scenario`; Redmine: `redmine_request`; Kaiten: `kaiten_get_card`).
- Produces: скилл `qaily:test-design`, автоматически подхватываемый из `skills/` (ключ `skills` в манифест НЕ добавлять — директория по умолчанию сканируется сама).

- [ ] **Step 1: Создать SKILL.md**

```markdown
---
name: test-design
description: Тест-дизайн по требованию: генерация тест-кейсов из задачи Redmine или карточки Kaiten с сохранением в Allure TestOps. Use when пользователь просит сгенерировать тест-кейсы, покрыть требование тестами, сделать тест-дизайн, написать кейсы по задаче.
---

# Тест-дизайн: генерация кейсов по требованию

## Входные данные

Определи источник требования из запроса пользователя:
- Номер задачи Redmine («задача №123») → прочитай через `redmine_request` (path `issues/123.json`, включи `include=journals,attachments`).
- Карточка Kaiten («карточка 456») → прочитай через `kaiten_get_card`.
- Текст требования прямо в запросе → используй как есть.

Целевой проект Allure: по умолчанию 35 (тестовый). Другой проект — только если пользователь указал явно.

## Процесс

1. **Прочитай требование целиком**: описание, критерии приёмки, комментарии. Неоднозначности перечисли пользователю ДО генерации — не выдумывай поведение системы.
2. **Проверь существующее покрытие**: `search_test_cases` по ключевым словам требования в целевом проекте. Найденные кейсы покажи — возможно, часть уже покрыта; дубли не создавай.
3. **Спроектируй кейсы** техниками тест-дизайна:
   - классы эквивалентности и граничные значения для входных данных;
   - позитивные И негативные сценарии (невалидный ввод, отказ смежной системы, права доступа);
   - состояния и переходы, если требование описывает workflow.
4. **Покажи пользователю таблицу кейсов** (название, приоритет, шаги кратко) и дождись подтверждения перед записью в Allure.
5. **После подтверждения** создай кейсы через `create_test_case`: название по шаблону «<Фича>. <Сценарий>», шаги как scenario, ожидаемый результат в каждом шаге. Тег с номером исходной задачи (например `redmine-123`).
6. **Отчитайся**: список созданных кейсов со ссылками вида `https://astbroker.qatools.cloud/project/35/test-cases/<id>`.

## Ограничения

- Без подтверждения пользователя ничего в Allure не создавать.
- В Redmine и Kaiten — только чтение, никаких изменений.
- Если `create_test_case` запрещён deny-масками — сообщи, что включён read-only режим, и выдай кейсы текстом.
```

- [ ] **Step 2: Проверить валидатором**

Run: `claude plugin validate . --strict`
Expected: успех, скилл распознан.

- [ ] **Step 3: Проверить срабатывание скилла**

Обновить локальную установку (`/plugin marketplace update qaily`, переустановить или `/reload-plugins`), затем в сессии: «сделай тест-дизайн по задаче №1 из Redmine».
Expected: Claude объявляет использование скилла `qaily:test-design`, читает задачу, показывает таблицу кейсов и ждёт подтверждения (в Allure без подтверждения ничего не пишет).

- [ ] **Step 4: Commit**

```bash
git add skills/test-design/SKILL.md
git commit -m "Скилл test-design: генерация кейсов из Redmine/Kaiten в Allure"
```

---

### Task 7: README под установку плагином

**Files:**
- Modify: `README.md` (переписать разделы установки; справочные разделы про read-only и проекты фазы 0 сохранить)

**Interfaces:**
- Consumes: команды установки из Task 3/4, deny-маски из Task 5.

- [ ] **Step 1: Переписать README**

Новая структура (полный текст разделов установки):

```markdown
# Qaily

QA AI-ассистент для команды на базе Claude Code: плагин со скиллами тест-дизайна и MCP-интеграциями (Allure TestOps, Redmine, Kaiten).

## Установка

Пререквизиты (один раз):

1. Claude Code ≥ 2.1.154: `claude --version`; обновить — `claude update`.
2. Node.js 20+: `brew install node` или [nodejs.org](https://nodejs.org).
3. uv (для Redmine MCP): `curl -LsSf https://astral.sh/uv/install.sh | sh`

Установка плагина — две команды в Claude Code:

    /plugin marketplace add <git-url-репозитория>
    /plugin install qaily@qaily

При включении Claude Code сам спросит токены (хранятся в системном keychain):

| Поле | Где взять |
|------|-----------|
| Allure TestOps API token | Allure TestOps → профиль → API tokens |
| Redmine API key | Redmine → Моя учётная запись → Ключ API. **Строго read-only ключ** |
| Kaiten API token | Kaiten → профиль → API-ключ |
| Kaiten space ID | опционально, можно оставить пустым |

Проверка: в сессии спросить «покажи тест-кейсы проекта 35 из Allure».

Доступ к репозиторию — по git (ssh-ключ или токен), как для обычного clone.

## Проверка токенов вручную

    curl -s -H "Authorization: Api-Token $ALLURE_TOKEN" "https://astbroker.qatools.cloud/api/rs/project" | head -c 200
    curl -s -H "X-Redmine-API-Key: $REDMINE_API_KEY" "https://redmine.fast-system.ru/users/current.json"
    curl -s -H "Authorization: Bearer $KAITEN_API_TOKEN" "https://lab-company.kaiten.ru/api/latest/users/current"

`401` — токен неверный.

## Если что-то не работает

- `/plugin` → qaily → статус компонентов; `claude mcp list` — статус серверов.
- Типовые причины: старый Claude Code, нет Node.js / uv, неверный токен (см. curl-проверки выше).
- Обновление плагина: `/plugin marketplace update qaily`.

## Ограничение записи (deny-маски)

Скопировать шаблон в свой рабочий проект (тот каталог, где запускается claude):

    mkdir -p .claude && cp <путь-к-этому-репо>/settings.local.json.example .claude/settings.local.json

Маски запрещают мутирующие инструменты Allure и Kaiten, установленные плагином.
Для сценария тест-дизайна (запись кейсов в тестовый проект 35) строки
`create_*` Allure из локального файла убираются.

Маски привязаны к именам инструментов плагина (`mcp__plugin_qaily_...`).
Если поднимать серверы НЕ через плагин (старый способ, project-scope .mcp.json) —
эти маски их не покроют.
```

Дальше в README сохранить без изменений разделы: «Проекты для обкатки (фаза 0)», объяснение read-only для Redmine (права токена, единственный инструмент `redmine_request`), «Пилотная группа». Разделы «Установка Allure/Redmine/Kaiten MCP» с ручными шагами — удалить (заменены установкой плагина); ссылку на vendor/README.md про пересборку бандлов сохранить одной строкой в конце.

- [ ] **Step 2: Проверить ссылки и полноту**

Прочитать README целиком: все упомянутые файлы существуют (`settings.local.json.example`, `vendor/README.md`), нет упоминаний удалённого `.mcp.json` и ручного экспорта токенов в `~/.zshrc` как основного пути.
Expected: противоречий нет.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "README: установка через плагин вместо ручной настройки MCP"
```

---

### Task 8: Релиз 0.1.0 и раскатка на пилот

**Files:**
- (изменений в коде нет; git push + проверка с чистой машины/каталога)

- [ ] **Step 1: Прогнать валидатор финально**

Run: `claude plugin validate . --strict`
Expected: успех.

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Чистая установка с git-источника**

Удалить локальную установку (`/plugin marketplace remove qaily`), затем поставить как поставит пилот:

```
/plugin marketplace add <git-url-репозитория>
/plugin install qaily@qaily
```

Expected: диалог токенов → серверы connected → запрос «покажи тест-кейсы проекта 35 из Allure» работает.

- [ ] **Step 4: Инструкция пилоту**

Отправить пилотной группе (2–3 QA) ссылку на README. Установка = пререквизиты + две команды. Собрать обратную связь: где споткнулись, чего не хватило в диалоге токенов.

**Дальнейшие релизы:** правка → bump `version` в `.claude-plugin/plugin.json` → commit + push → у команды `/plugin marketplace update qaily`. Без bump'а версии обновление считается по SHA коммита.
