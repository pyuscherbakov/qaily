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
команде установленного пакета. Следующий этап настройки должен создать ровно
одно активное top-level подключение `qaily_testops` с абсолютным helper path из
`installedPath`, URL и политиками на том же подключении. После обновления
пакета путь необходимо обновлять. Не включайте bundled `testops` параллельно.

Автоматическая настройка, перенос QA-инструкций на Codex, write policies и
реальное выполнение скиллов будут завершены на следующих этапах. Запись в
сервисы и безопасный полный рабочий сценарий Codex пока не подтверждены;
`doctor` в текущей версии ещё содержит инструкции для Claude. Не запускайте
`headers` как диагностику: его stdout содержит заголовки авторизации.

Проверка упаковки использует отдельный синтетический профиль и копию пакета,
где все внешние MCP заменены локальным fixture. Обнаружение файлов в cache
не доказывает выполнение скилла моделью, работу токенов или enforcement policy.
