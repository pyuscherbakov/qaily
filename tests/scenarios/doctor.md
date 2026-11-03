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
