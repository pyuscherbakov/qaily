# Qaily в Codex

Пакет `qaily` версии `0.5.0` предназначен для приватного marketplace
`qaily-codex`. Claude Code продолжает использовать `.claude-plugin/plugin.json`
и `mcp-servers.json`; Codex использует совместимый `.codex-plugin/plugin.json`
и `.mcp.json`. Корневые portable `plugin.json` и `mcp.json` не требуются.

## Проверенная установка из локального marketplace

На macOS проверен Codex CLI `0.166.0-alpha.5.1`. Это проверенная версия,
а не заявленная минимальная. В терминале, где доступен `codex`, выполните:

```sh
codex plugin marketplace add /absolute/path/to/qaily --json
codex plugin add qaily@qaily-codex --json
codex plugin list --json
```

Замените `/absolute/path/to/qaily` на путь к клону репозитория; путь с пробелами
заключите в кавычки. `source.path` в `.agents/plugins/marketplace.json`
отсчитывается от корня marketplace. Клиент копирует пакет в свой plugin cache;
ответ установки содержит `installedPath`. Исходный checkout не должен быть cwd
для обнаружения скиллов. Доступны шесть имён: `test-design`,
`coverage-gap-design`, `review-testcase`, `review-autotest`, `launch-triage`, `doctor`.
В нативном каталоге клиента они отображаются с префиксом `qaily:`, например
`qaily:test-design`.

Для приватного Git marketplace локальный клон можно получить обычными средствами
Git с уже настроенной аутентификацией. Прямая установка и обновление по Git URL,
Windows/Linux и desktop UI пока не проверены. Не передавайте credentials в URL.

## Ограничения текущего этапа

Упаковка содержит семь MCP ID: `testops`, `redmine`, `kaiten`, `context7`,
`playwright`, `chrome-devtools`, `jam`. Зависимости закреплены так же, как для
Claude. MCP могут запускать внешние процессы или обращаться к сервисам при
начале сессии; установка пакета не подтверждает их работоспособность.
Пять stdio подключений используют `cwd: "."` относительно установленного
cache и `./bin/qaily_launch.py`. Этот способ разрешения пути проверен
нативным клиентом на fixture из каталога с пробелами и Unicode; переменные
`${PLUGIN_ROOT}` и `${CLAUDE_PLUGIN_ROOT}` в compatibility args не раскрываются.

Bundled `testops` явно отключён (`enabled: false`), helper для него отсутствует.
Codex не раскрывает `${PLUGIN_ROOT}` и `${CLAUDE_PLUGIN_ROOT}` в HTTP helper
команде установленного пакета. Настройка ниже создаёт ровно
одно активное top-level подключение `qaily_testops` с абсолютным helper path из
`installedPath`, URL и политиками на том же подключении. После обновления
пакета путь необходимо обновлять. Не включайте bundled `testops` параллельно.

Перенос QA-инструкций на Codex, write policies и
реальное выполнение скиллов будут завершены на следующих этапах. Запись в
сервисы и безопасный полный рабочий сценарий Codex пока не подтверждены;
`doctor` в текущей версии ещё содержит инструкции для Claude. Не запускайте
`headers` как диагностику: его stdout содержит заголовки авторизации.

Проверка упаковки использует отдельный синтетический профиль и копию пакета,
где все внешние MCP заменены локальным fixture. Обнаружение файлов в cache
не доказывает выполнение скилла моделью, работу токенов или enforcement policy.

## Настройка адресов и TestOps

Необязательный файл `~/.qaily/config.json` содержит только несекретные базовые
адреса; допустимы `testops_url`, `redmine_url`, `kaiten_url`. Пример:

```json
{"redmine_url": "http://127.0.0.1:8765/base"}
```

Без файла используются адреса из пакета. Не добавляйте токены, userinfo, query
или fragment. Базовый путь сохраняется; endpoint добавляется автоматически.
Redmine и Kaiten используют эти настройки и при запуске, и при проверке `check`.
Токены хранятся отдельно в keyring или `QAILY_<NAME>`, как и прежде.

После установки найдите `installedPath` в выводе `codex plugin add`, затем
выполните (подставив путь к установленной копии):

```sh
python3 "/absolute/installedPath/bin/qaily_setup.py" render --package-root "/absolute/installedPath"
```

Команда только печатает несекретный TOML. Вручную внесите его в фактический
`~/.codex/config.toml`: при повторной настройке обновите существующие таблицы,
а не добавляйте их второй раз. Bundled `testops` должен оставаться отключён;
единственный активный сервер TestOps — `qaily_testops`, с URL, helper и
`default_tools_approval_mode = "prompt"` в одной таблице. Остальные серверы
остаются в пакете. Не копируйте этот фрагмент повторно целиком: TOML не допускает
дублирующиеся таблицы. После marketplace update снова возьмите актуальный
`installedPath` и замените путь helper: старый cache может исчезнуть.

На проверенном Codex CLI 0.166.0-alpha.5.1 изолированный app-server не передал
`QAILY_ALLURE` из своего окружения в процесс HTTP helper; это ограничение нельзя
считать исправленным настройкой выше. Проверка с контролируемой синтетической
передачей токена доказала подключение и чтение через helper; реальный keyring
и его доступность из Codex пока не проверены. Не выводите результат `headers`
в чат: stdout содержит авторизацию. Политика подтверждения записи также ещё
не проверена в действии; настройка `prompt` сама по себе этого не доказывает.
