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

Bundled `testops` включён и использует официальный HTTP endpoint. По данным пользователя endpoint доступен только из РФ. Установка не подтверждает доступ к сети, токен или работу MCP.

## Настройка адресов и TestOps

Необязательный `~/.qaily/config.json` содержит только базовые URL `testops_url`, `redmine_url`, `kaiten_url`, без токенов, userinfo, query и fragment. Redmine и Kaiten используют адреса и при запуске, и при проверке. Секреты задаются отдельно через keyring или `QAILY_<NAME>`. Не запускайте `headers` для диагностики: stdout содержит авторизацию.

Для Codex stdio передаются только `QAILY_REDMINE`, `QAILY_KAITEN` и `QAILY_CONTEXT7` соответствующим процессам. Синтетическая проверка `env_vars` не подтверждает работу реальных секретов или сервисов.

Необязательный альтернативный top-level TestOps создаётся командой:

```sh
python3 "/absolute/installedPath/bin/qaily_setup.py" render --package-root "/absolute/installedPath"
```

Команда печатает несекретный TOML; вручную объедините его с `~/.codex/config.toml` без повторения таблиц. Фрагмент отключает bundled TestOps, чтобы избежать дубликата, и задаёт `env_http_headers.Authorization = "QAILY_TESTOPS_AUTHORIZATION"`. Пользователь отдельно задаёт в окружении процесса Codex **полный** заголовок `Api-Token ...`; не помещайте его в config, чат или логи. `QAILY_ALLURE` и keyring автоматически в него не преобразуются. На Codex CLI 0.166.0-alpha.5.1 этот механизм проверен с синтетическим локальным MCP и фиктивным заголовком; реальные токены, сервис, другие версии и безопасность распространения окружения не проверены.

Режим `--auth-mode keyring-helper` сохраняет альтернативу с абсолютным путём helper; доступ реального keyring из Codex не подтверждён. После обновления пакета проверьте и при необходимости обновите путь в применённой конфигурации. Runtime enforcement policy, реальные дочерние процессы и Claude этой проверкой не подтверждены.

## Политика доступа

`render` выше — необязательный вариант с top-level `qaily_testops`: он отключает
bundled `testops` только при применении этого варианта, чтобы не создавать два
подключения. Из коробки активен официальный bundled HTTP endpoint. По словам
пользователя, он доступен только из России; доступность сети и авторизация —
разные проверки. Рабочий helper и реальный keyring пока не подтверждены. В package заданы `prompt` для TestOps и списки чтения Kaiten/Context7; Jam
пока имеет пустой список. Фильтрация списков проверена на native fixture,
но подтверждения bundled TestOps в действии ещё не проверены. Проверка policy
обязательна до выполнения записи.

`python3 /absolute/installedPath/bin/qaily_setup.py policy --catalog catalog.json`
печатает дополнительный фрагмент для проверенного снимка каталога. `catalog.json` — объект service → массив точных
имён из `tools/list`; данные каталога не должны содержать секретов. Генератор
пересекает каталог с `references/policies/read-tools.json`. У TestOps действует
prompt по умолчанию, проверенные чтения получают `approve`; Kaiten, Context7 и Jam получают только пересечение списков.
По умолчанию policy относится к bundled `testops` в `qaily@qaily-codex`.
Если применён необязательный `render`, добавьте к команде `policy` параметр
`--testops-connection top-level`: таблицу `mcp_servers.qaily_testops` нужно
объединить с таблицей из `render`, а не добавлять второй раз. Plugin policy
не применяется к top-level TestOps. Проверенные по исходникам pinned Kaiten и Context7
чтения перечислены в реестре; TestOps и Jam ожидают аудита каталога. Отсутствие
каталога означает пустой allowlist, и чтение этих серверов будет недоступно.

Проверяйте активную конфигурацию и фактические MCP ID в клиенте, затем проводите
сценарий `tests/scenarios/access-policy.md` на фиктивном сервере. Наличие TOML
само по себе не подтверждает применение: bypass режима подтверждений не является
проверкой. Если enforcement не подтверждён, не выполняйте запись. `REDMINE_READ_ONLY=1`
сохраняется, но общий `redmine_request` может принимать разные HTTP-методы:
одним именем инструмента нельзя гарантировать запрет записи. Требуются проверка
ограничений сервера и read-only токен; до неё запрет записи не подтверждён.
