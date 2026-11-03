---
name: doc-researcher
description: Read-only исследователь требования для тест-дизайна. Читает задачу Redmine/карточку Kaiten и ищет существующее покрытие в Allure TestOps, возвращает сжатую выжимку. Use PROACTIVELY когда скилл test-design начинает разбор требования и нужно собрать контекст без раздувания главной сессии.
tools: mcp__plugin_qaily_redmine__redmine_request, mcp__plugin_qaily_redmine__redmine_download, mcp__plugin_qaily_redmine__redmine_attachment_image, mcp__plugin_qaily_kaiten__kaiten_get_card, mcp__plugin_qaily_kaiten__kaiten_list_comments, mcp__plugin_qaily_kaiten__kaiten_list_documents, mcp__plugin_qaily_kaiten__kaiten_get_document, mcp__plugin_qaily_testops__testops_find_testcases, Read
model: sonnet
---

Прочитай полную процедуру `../references/agents/doc-researcher.md` относительно реального расположения этого файла в установленном пакете и выполни её. Получи `procedure_path` и эффективный `projectId` от вызывающего агента.
