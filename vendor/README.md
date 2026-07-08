# vendor/ — собранные MCP-серверы

Однофайловые esbuild-бандлы наших форков MCP-серверов. Зависимости зашиты внутрь: для запуска нужен только Node.js, без git, npm-установки и сборки на машине пользователя.

| Файл | Источник | Коммит |
|------|----------|--------|
| `allure-testops-mcp.mjs` | [pyuscherbakov/allure-testops-mcp](https://github.com/pyuscherbakov/allure-testops-mcp) | `5ff190e567bba4db689995bd578fd58ca9eeec43` |

Kaiten MCP не вендорится: это Python-пакет, ставится через `uvx` напрямую из git (пин по коммиту — в `mcp-servers.json`). Наш форк [pyuscherbakov/kaiten-mcp](https://github.com/pyuscherbakov/kaiten-mcp) от [ViktorOgnev/kaiten-mcp](https://github.com/ViktorOgnev/kaiten-mcp) — форк убирает зависимость от чужого репо и даёт место под свои патчи. Python-бандлинг (аналог esbuild) для single-file не применяется.

## Как пересобрать (при обновлении форка)

```sh
git clone <репозиторий форка> && cd <форк>
git checkout <нужный коммит>
npm install          # prepare-скрипт запустит tsc → dist/
npx -y esbuild dist/index.js --bundle --platform=node --format=esm \
  --outfile=<имя>.mjs \
  --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"
```

Полученный `.mjs` положить сюда, обновить SHA коммита в таблице выше. Баннер с `createRequire` обязателен: без него CJS-зависимости внутри ESM-бандла падают с «Dynamic require is not supported».

Быстрая проверка бандла — сервер должен ответить JSON-ом на `initialize`:

```sh
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | <нужные env-переменные> node <имя>.mjs
```
