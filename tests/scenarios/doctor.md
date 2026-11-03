# Doctor: ручные read-only сценарии

Во всех сценариях использовать фиктивные данные, не выводить секреты и не вызывать записи.

- HTTP 200 при отключённом MCP: HTTP ok, initialize/catalog/read not_checked; не утверждать MCP ok.
- Нет uv: dependency error с инструкцией установки; остальные независимые результаты сохранить.
- Jam требует auth: MCP not_checked, предложить OAuth через клиент.
- Нет Secret Service: secret error для обязательных ключей, предложить переменные окружения; Context7 необязателен.
- Sandbox запрещает каталог вложений: error или not_checked с причиной; не расширять права и не обходить sandbox.
- Browser MCP недоступен: dependency not_checked/error; review-testcase без browser остаётся доступен.
- Policy задана в конфигурации: config ok, runtime policy not_checked до наблюдаемой проверки без bypass.
- Применённый helper указывает на удалённый cache: config error; без TOML parser — not_checked.
- Отсутствует или недоступен файл установленного плагина: отдельный результат resources error/not_checked, без чтения вне разрешённой области и без обхода sandbox; browser проверяется отдельно.
- Codex top-level native: только полный синтетический `QAILY_TESTOPS_AUTHORIZATION`, только raw `QAILY_ALLURE`, оба, неизвестная среда процесса — native выбирается по конфигурации, raw не используется автоматически; без известной среды not_checked.
- После применения URL A settings указывает B, либо bundled с фиксированным URL и override B, либо два активных подключения, испорченный TOML или Python 3.10 без TOML parser: не представлять результат HTTP по B как состояние активного A; несовпадение/неизвестность not_checked, дубликат/испорченный TOML error.
