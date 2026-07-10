# План: модернизация скилла review-testcase (шаги через API + исправления)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать ревью шагов тест-кейса работоспособным (сейчас `get_test_case_scenario` возвращает пусто для ручных кейсов) и устранить найденные при анализе дефекты SKILL.md.

**Architecture:** Два репозитория. Фаза A — форк `~/code/allure-testops-mcp`: три новых read-only инструмента поверх недокументированных эндпоинтов, которыми пользуется фронт ТестОпса (`/api/testcase/{id}/step`, `/api/sharedstep/{id}`, `/api/sharedstep/{id}/step`). Фаза B — репо qaily: пересборка vendor-бандла и переработка `skills/review-testcase/SKILL.md` (источники данных, канонические имена блоков, fallback при недоступных шагах).

**Tech Stack:** TypeScript + vitest + esbuild (MCP-форк), Markdown-скилл (qaily), Node.js 20+.

## Global Constraints

- Коммиты — на русском, без `Co-Authored-By` (глобальное правило пользователя).
- Все новые MCP-инструменты — read-only (`annotations: { readOnlyHint: true }`) и добавлены в пиновый список `EXPECTED_READ_ONLY`.
- Скилл ревью read-only: ничего в TestOps не изменяет.
- Файлы < 500 строк.
- Скилл применения правок НЕ планируется — упоминание «машиночитаемого входа» из SKILL.md убрать, но единый формат блоков сохранить.
- Живые кейсы для проверки: 40041 (параметризация, 3 значения `ФормаОплаты`), 39979 (общие шаги). У обоих `hasManualScenario: true`, а `/scenario` пуст — это и есть воспроизведение бага.

---

## Фаза A: allure-testops-mcp (`/Users/pavelshcherbakov/code/allure-testops-mcp`)

### Task 1: инструмент `get_test_case_steps`

**Files:**
- Modify: `src/api/test-cases.ts` (рядом с `getTestCaseScenario`, ~строка 153)
- Modify: `src/tools/test-cases.ts` (описание рядом с `get_test_case_scenario` ~строка 353, хендлер ~строка 686)
- Modify: `tests/unit/tools/test-cases.unit.test.ts`
- Modify: `tests/unit/server-bootstrap.unit.test.ts` (список `EXPECTED_READ_ONLY`, ~строка 44)

**Interfaces:**
- Produces: `getTestCaseSteps(client: AllureApiClient, id: number): Promise<unknown>`; MCP-тул `get_test_case_steps` со схемой `{ id: number }` (required).

- [ ] **Step 1: падающий unit-тест**

В `tests/unit/tools/test-cases.unit.test.ts`: добавить `getTestCaseSteps: vi.fn(),` в мок модуля api (рядом с `getTestCaseScenario: vi.fn(),` ~строка 24) и тест по образцу соседнего (блок «overview/history/scenario handlers forward expected arguments», ~строка 141):

```ts
it("get_test_case_steps forwards id", async () => {
  vi.mocked(api.getTestCaseSteps).mockResolvedValueOnce({});
  await bundle.handlers.get_test_case_steps({ id: 20 });
  expect(api.getTestCaseSteps).toHaveBeenCalledWith(client, 20);
});
```

В `tests/unit/server-bootstrap.unit.test.ts` добавить `"get_test_case_steps",` в `EXPECTED_READ_ONLY` (секция `// test cases`, после `"get_test_case_scenario",`).

- [ ] **Step 2: убедиться, что тесты падают**

Run: `cd /Users/pavelshcherbakov/code/allure-testops-mcp && npx vitest run tests/unit`
Expected: FAIL — `getTestCaseSteps` не существует / тул не зарегистрирован.

- [ ] **Step 3: реализация**

`src/api/test-cases.ts`, после `getTestCaseScenario`:

```ts
export function getTestCaseSteps(client: AllureApiClient, id: number): Promise<unknown> {
  return client.get(`/api/testcase/${id}/step`);
}
```

`src/tools/test-cases.ts` — определение тула сразу после `get_test_case_scenario` (~строка 361):

```ts
{
  name: "get_test_case_steps",
  description:
    "Get design-time scenario steps for a test case (works for manual test cases where get_test_case_scenario returns empty; steps may reference shared steps via sharedStepId).",
  inputSchema: {
    type: "object" as const,
    properties: { id: { type: "number" } },
    required: ["id"],
  },
  annotations: { readOnlyHint: true },
},
```

Хендлер — после `get_test_case_scenario` (~строка 689):

```ts
get_test_case_steps: async (rawArgs: unknown) => {
  const args = asObject(rawArgs);
  return api.getTestCaseSteps(client, getRequiredId(args));
},
```

- [ ] **Step 4: тесты зелёные**

Run: `npx vitest run tests/unit`
Expected: PASS.

- [ ] **Step 5: коммит**

```bash
git add src/api/test-cases.ts src/tools/test-cases.ts tests/unit
git commit -m "feat: инструмент get_test_case_steps — шаги ручного кейса через /api/testcase/{id}/step"
```

### Task 2: инструменты общих шагов `get_shared_step`, `get_shared_step_steps`

**Files:**
- Create: `src/api/shared-steps.ts`
- Create: `src/tools/shared-steps.ts`
- Modify: `src/server-bootstrap.ts` (регистрация бандла, ~строки 2–6 и 31–36)
- Create: `tests/unit/tools/shared-steps.unit.test.ts`
- Modify: `tests/unit/server-bootstrap.unit.test.ts` (`EXPECTED_READ_ONLY`)

**Interfaces:**
- Consumes: `AllureApiClient` из `src/client.ts`, `asObject`/`getRequiredId` из `src/tools/utils.ts` (см. импорты в `src/tools/test-cases.ts`), типы `McpToolDefinition`/`ToolHandler` из `src/tools/types.ts`.
- Produces: `createSharedStepTools(client)` — бандл формата `{ tools, handlers }`, как `createTestCaseTools`; тулы `get_shared_step` и `get_shared_step_steps` со схемой `{ id: number }`.

- [ ] **Step 1: падающий unit-тест**

`tests/unit/tools/shared-steps.unit.test.ts` — по образцу `test-cases.unit.test.ts` (мок `../../src/api/shared-steps.js`):

```ts
it("shared step handlers forward id", async () => {
  vi.mocked(api.getSharedStep).mockResolvedValueOnce({});
  vi.mocked(api.getSharedStepSteps).mockResolvedValueOnce({});
  await bundle.handlers.get_shared_step({ id: 7 });
  await bundle.handlers.get_shared_step_steps({ id: 7 });
  expect(api.getSharedStep).toHaveBeenCalledWith(client, 7);
  expect(api.getSharedStepSteps).toHaveBeenCalledWith(client, 7);
});
```

В `EXPECTED_READ_ONLY` — новая секция:

```ts
// shared steps
"get_shared_step",
"get_shared_step_steps",
```

- [ ] **Step 2: убедиться, что тесты падают**

Run: `npx vitest run tests/unit`
Expected: FAIL — модуль `shared-steps` не существует.

- [ ] **Step 3: реализация**

`src/api/shared-steps.ts`:

```ts
import { AllureApiClient } from "../client.js";

export function getSharedStep(client: AllureApiClient, id: number): Promise<unknown> {
  return client.get(`/api/sharedstep/${id}`);
}

export function getSharedStepSteps(client: AllureApiClient, id: number): Promise<unknown> {
  return client.get(`/api/sharedstep/${id}/step`);
}
```

`src/tools/shared-steps.ts` — структура и импорты по образцу `src/tools/test-plans.ts` (самый маленький бандл):

```ts
import { AllureApiClient } from "../client.js";
import * as api from "../api/shared-steps.js";
import { McpToolDefinition, ToolHandler } from "./types.js";
import { asObject, getRequiredId } from "./utils.js";

export function createSharedStepTools(client: AllureApiClient): {
  tools: McpToolDefinition[];
  handlers: Record<string, ToolHandler>;
} {
  const tools: McpToolDefinition[] = [
    {
      name: "get_shared_step",
      description: "Get a shared step by ID (name and metadata).",
      inputSchema: {
        type: "object" as const,
        properties: { id: { type: "number" } },
        required: ["id"],
      },
      annotations: { readOnlyHint: true },
    },
    {
      name: "get_shared_step_steps",
      description:
        "Get the steps that make up a shared step. Use to expand sharedStepId references returned by get_test_case_steps.",
      inputSchema: {
        type: "object" as const,
        properties: { id: { type: "number" } },
        required: ["id"],
      },
      annotations: { readOnlyHint: true },
    },
  ];

  const handlers: Record<string, ToolHandler> = {
    get_shared_step: async (rawArgs: unknown) => {
      const args = asObject(rawArgs);
      return api.getSharedStep(client, getRequiredId(args));
    },
    get_shared_step_steps: async (rawArgs: unknown) => {
      const args = asObject(rawArgs);
      return api.getSharedStepSteps(client, getRequiredId(args));
    },
  };

  return { tools, handlers };
}
```

Перед реализацией сверить фактические сигнатуры бандла и `getRequiredId` с `src/tools/test-plans.ts` — если бандл там возвращает другой тип (например, `handlers` как `Map`), повторить его.

`src/server-bootstrap.ts` — импорт и регистрация:

```ts
import { createSharedStepTools } from "./tools/shared-steps.js";
// ...
const bundles = [
  createTestCaseTools(client),
  createSharedStepTools(client),
  createLaunchTools(client),
  createTestResultTools(client),
  createTestPlanTools(client),
];
```

- [ ] **Step 4: все тесты зелёные + линт + каталог тулов**

Run: `npx vitest run && npm run lint && npm run docs:generate`
Expected: PASS; `docs/tools.json` обновился (3 новых тула).

- [ ] **Step 5: коммит**

```bash
git add src/api/shared-steps.ts src/tools/shared-steps.ts src/server-bootstrap.ts tests/unit docs/tools.json
git commit -m "feat: инструменты get_shared_step и get_shared_step_steps"
```

### Task 3: версия, сборка, пуш

**Files:**
- Modify: `package.json` (`"version": "1.1.0"` → `"1.2.0"`)
- Modify: `README.md` (строка 15: добавить «steps» и «shared steps» в перечень возможностей)

- [ ] **Step 1: bump версии и README**

В `package.json`: `"version": "1.2.0"`. В `README.md` строку возможностей дополнить: `- Test cases: ..., scenario, steps, shared steps, tags, issues, custom fields`.

- [ ] **Step 2: полная проверка**

Run: `npm run build && npx vitest run && npm run lint`
Expected: сборка и тесты зелёные.

- [ ] **Step 3: коммит и пуш**

```bash
git add package.json README.md
git commit -m "chore: версия 1.2.0 — инструменты шагов и общих шагов"
git push origin main
git rev-parse HEAD   # SHA понадобится для vendor/README.md в qaily
```

Пуш — в собственный форк `pyuscherbakov/allure-testops-mcp`; без него не обновить SHA в таблице вендора.

---

## Фаза B: qaily (`/Users/pavelshcherbakov/code/work/ast/qaily`)

### Task 4: пересборка vendor-бандла

**Files:**
- Modify: `vendor/allure-testops-mcp.mjs` (перегенерация)
- Modify: `vendor/README.md` (SHA в таблице)

**Interfaces:**
- Consumes: SHA коммита из Task 3.

- [ ] **Step 1: собрать бандл из локального форка**

```bash
cd /Users/pavelshcherbakov/code/allure-testops-mcp
npm run build
npx -y esbuild dist/index.js --bundle --platform=node --format=esm \
  --outfile=/Users/pavelshcherbakov/code/work/ast/qaily/vendor/allure-testops-mcp.mjs \
  --banner:js="import { createRequire } from 'module'; const require = createRequire(import.meta.url);"
```

Баннер обязателен (без него CJS-зависимости падают с «Dynamic require is not supported» — см. vendor/README.md).

- [ ] **Step 2: smoke-тест бандла**

```bash
cd /Users/pavelshcherbakov/code/work/ast/qaily
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | ALLURE_TESTOPS_URL=https://astbroker.qatools.cloud ALLURE_TOKEN=dummy ALLURE_PROJECT_ID=35 node vendor/allure-testops-mcp.mjs | head -c 200
```

Expected: JSON-ответ на `initialize`. Дополнительно убедиться, что новые тулы в бандле: `rtk proxy grep -c "get_test_case_steps\|get_shared_step" vendor/allure-testops-mcp.mjs` → > 0.

- [ ] **Step 3: обновить SHA в vendor/README.md**

В таблице заменить `5ff190e567bba4db689995bd578fd58ca9eeec43` на SHA из Task 3.

- [ ] **Step 4: коммит**

```bash
git add vendor/allure-testops-mcp.mjs vendor/README.md
git commit -m "vendor: обновить allure-testops-mcp — инструменты шагов и общих шагов"
```

### Task 5: живая проверка новых инструментов

Ручной чекпойнт — MCP-бандл подхватывается только новой сессией Claude Code.

- [ ] **Step 1:** перезапустить сессию Claude Code с плагином qaily (переустановить/обновить плагин, если ставится из кэша маркетплейса, а не по симлинку).
- [ ] **Step 2:** вызвать `get_test_case_steps(40041)` → непустой список шагов (в UI шаги есть, `hasManualScenario: true`).
- [ ] **Step 3:** вызвать `get_test_case_steps(39979)` → среди шагов есть элемент с `sharedStepId`; для него `get_shared_step_steps(<sharedStepId>)` → непустое содержимое.
- [ ] **Step 4:** зафиксировать фактическую форму ответа (имена полей: `bodyJson`, `expectedResultId`, `attachmentId`, `sharedStepId`, `children` — выведено из кода фронта, требует подтверждения). Если поля отличаются — поправить формулировки в Task 6 Step 2 перед его выполнением.

### Task 6: переработка SKILL.md

**Files:**
- Modify: `skills/review-testcase/SKILL.md`

**Interfaces:**
- Consumes: имена тулов из фазы A: `get_test_case_overview`, `get_test_case_steps`, `get_shared_step`, `get_shared_step_steps`.

Все правки — точечные Edit. Номера строк — по текущему файлу (253 строки).

- [ ] **Step 1: раздел «Входные данные» — обработка ошибок**

После строки `` `testcase_id` — из запроса пользователя (номер или ссылка вида `.../test-cases/<id>`). `` добавить:

```markdown
Если кейс по ID не найден или API вернул ошибку — сообщи об этом пользователю и останови ревью. Не продолжай по частичным данным.
```

- [ ] **Step 2: раздел «Алгоритм», шаг 1 — источники данных**

Заменить текущий шаг 1 (строка 219):

```markdown
1. **Получи данные кейса** двумя вызовами:
   - `get_test_case_overview` — имя, описание, предусловие, ожидаемый результат, статус, длительность (`duration`), участники с ролями (`members`), связанные задачи (`issues`), приоритет (`customFields`), параметры и их значения (`parameters` + `examples`). Отдельные вызовы `get_test_case`, `get_test_case_issues`, `get_test_case_custom_fields` не нужны — overview покрывает всё.
   - `get_test_case_steps` — шаги сценария. Порядок шагов — `root.children`, содержимое — `scenarioSteps` (map id → шаг, текст шага в `body`, параметры в тексте как `{{Имя}}`). Шаг с `sharedStepId` — общий шаг: его название — в `sharedSteps`, содержимое — в `sharedStepScenarioSteps` того же ответа; дополнительные вызовы не нужны.
   - Если `get_test_case_steps` недоступен или вернул пустой `scenarioSteps` при `hasManualScenario: true` — блоки 7–8 не проверяй и явно напиши в начале ответа: «Шаги кейса недоступны через API — блоки 7 (Сценарий) и 8 (Ожидаемый результат) не проверены». Молча пропускать нельзя. (`get_test_case_scenario` для ручных кейсов без запусков всегда пуст — не используй его.)
```

- [ ] **Step 3: канонические имена блоков**

Единые имена в замечаниях и правках: `1. Наименование` и `7. Сценарий`. Правки:
- строка 44: `1. Имя тест-кейса` → `1. Наименование`
- строка 48: `1. Имя тест-кейса` → `1. Наименование`
- строка 151: `7. Шаги` → `7. Сценарий`
- строка 156: `7. Шаги` → `7. Сценарий`
- строка 223: `1. Имя тест-кейса` → `1. Наименование`
- строка 231: `1. Имя тест-кейса` → `1. Наименование`

- [ ] **Step 4: одна сводная секция правок**

Строку 237 (`Секция «Предлагаемые правки» — в том же формате с номерами блоков: она машиночитаемый вход для скилла применения правок.`) заменить на:

```markdown
Секция «Предлагаемые правки» — одна на весь ответ, в том же формате с номерами блоков. Поблочные примеры с заголовком «Правка:» выше — иллюстрации формата; в финальном ответе не выводи отдельные «Правка:» по блокам, собери всё в единую секцию «Предлагаемые правки».
```

- [ ] **Step 5: источники данных в блоках 2, 6, 9, 10**

- Блок 2, строка 58: `Проверь наличие этих ФИО в поле «Участники» кейса (обязательно!).` → `Проверь наличие этих ФИО среди участников кейса — массив ` + `` `members` `` + ` из overview (обязательно!).`
- Блок 6, строка 124: после `**«Ревьювер» и «Назначен» обязательны.**` добавить: `Роли — в ` + `` `members[].role.name` `` + ` из overview; роль «Owner» — автор кейса, она не заменяет «Ревьювер» и «Назначен».`
- Блок 9, строка 189: `Проверяй только если в кейсе есть параметры` + `` `{{...}}` `` + ` (3.13):` → `Проверяй только если у кейса есть параметры — массив ` + `` `parameters` `` + ` в overview и/или плейсхолдеры ` + `` `{{...}}` `` + ` в тексте (3.13). Значения параметров — в ` + `` `examples` `` + ` overview.`
- Блок 10, строка 210: `По данным ` + `` `get_test_case` `` + ` и ` + `` `get_test_case_custom_fields` `` + `:` → `По данным overview:` — и в списке ниже уточнить: приоритет — `customFields` с именем «Приоритет»; длительность — `duration` (0 = не указана, замечание); статус — `status.name`.

- [ ] **Step 6: мелочи**

- Строка 92: `Активный залог:` → `Нарушение — действие вместо состояния:`
- Кавычки: заменить смешанные пары `„...\"` (открывающая „, закрывающая прямая ") на «ёлочки» по всему файлу — строки 41, 88, 140, 147, 170, 174 и пример в блоке 8. Внутренние кавычки в цитатах-эталонах оставить «...».

- [ ] **Step 7: перечитать файл целиком**

Проверить: нигде не осталось `get_test_case_scenario`, `get_test_case_issues`, `get_test_case_custom_fields` как источников (упоминание scenario допустимо только в предупреждении из Step 2); имена блоков единые; файл < 500 строк.

- [ ] **Step 8: коммит**

```bash
git add skills/review-testcase/SKILL.md
git commit -m "review-testcase: шаги через get_test_case_steps, единый формат блоков, fallback без шагов"
```

### Task 7: сквозная проверка скилла

Ручной чекпойнт.

- [ ] **Step 1:** в новой сессии выполнить ревью кейса 40041 скиллом. Ожидаемо: замечания по шагам (блок 7) присутствуют — шаги получены; параметризация проверена по 3 значениям `ФормаОплаты`; участники найдены (Owner/Назначен/Ревьювер).
- [ ] **Step 2:** ревью кейса 39979. Ожидаемо: общий шаг развёрнут через `get_shared_step_steps`; замечания минимум по трём пунктам: опечатка в названии («Отображ**а**ние»), пустое предусловие, нулевая длительность.
- [ ] **Step 3:** убедиться, что в ответах нет секций без замечаний и нет поблочных «Правка:» — только одна секция «Предлагаемые правки».
- [ ] **Step 4:** запушить qaily: `git push origin main`.

---

## Риски

- Форма ответа `/api/testcase/{id}/step` выведена из минифицированного кода фронта, не из живого ответа. Task 5 — обязательный чекпойнт перед Task 6; при расхождении сначала правится текст Step 2/Step 5 в Task 6.
- Эндпоинты недокументированные — могут измениться при обновлении ТестОпса. Фиксируем в vendor/README.md привязку к SHA форка; при поломке ревью скилл честно сообщит «шаги недоступны» (fallback из Task 6 Step 2).
- `git push` в форк и в qaily — внешние действия; выполняются в рамках плана после подтверждения плана пользователем.
