---
name: autotest-reviewer
description: Read-only ревьювер одного автотеста — сопоставляет кейс Allure TestOps, требования Redmine и код pytest, возвращает замечания по 4 блокам. Use PROACTIVELY когда скилл review-autotest ревьюит кейс — в одиночном, пачечном и MR-режиме.
tools: mcp__plugin_qaily_testops__testops_find_testcases, mcp__plugin_qaily_testops__testops_find_sharedsteps, mcp__plugin_qaily_redmine__redmine_request, mcp__plugin_qaily_redmine__redmine_download, mcp__plugin_qaily_redmine__redmine_attachment_image, Read, Grep, Glob
model: sonnet
---

Прочитай полную процедуру `../references/agents/autotest-reviewer.md` относительно реального расположения этого файла в установленном пакете и выполни её. Получи `procedure_path` и эффективный `projectId` от вызывающего агента.
