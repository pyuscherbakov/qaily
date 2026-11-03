# Safe local Codex capability probe

Run this gate before choosing the Codex package format. A successful install or
accepted config is not evidence of MCP authorization or approval enforcement.
Use synthetic data only. Do not start qaily's real service connections.

## Fixture contract

`tests/integration/fake_mcp.py` uses only Python's standard library:

```text
python3 tests/integration/fake_mcp.py --transport stdio --host 127.0.0.1 --port 0 --journal JOURNAL --fixture FIXTURE
python3 tests/integration/fake_mcp.py --transport http --host 127.0.0.1 --port 0 --journal JOURNAL --fixture FIXTURE
```

Use a different journal for every simultaneous process. Each process truncates
its journal on startup. HTTP prints a readiness line `{"url":"http://127.0.0.1:PORT/mcp"}`;
stdio emits only newline-delimited JSON-RPC replies. Always terminate subprocesses
in teardown. Only numeric IPv4 loopback bind addresses are accepted.

A minimal fixture:

```json
{
  "tools": [
    {
      "name": "read_item",
      "description": "Read a synthetic item",
      "inputSchema": {"type": "object", "properties": {}},
      "annotations": {"readOnlyHint": true}
    },
    {
      "name": "write_item",
      "description": "Write a synthetic item",
      "inputSchema": {"type": "object", "properties": {}},
      "annotations": {"readOnlyHint": false}
    }
  ],
  "responses": {
    "read_item": [{"content": [{"type": "text", "text": "fixture item"}]}],
    "write_item": [{"content": [{"type": "text", "text": "fixture written"}]}]
  },
  "required_authorization": "Api-Token fixture-value"
}
```

`required_authorization` accepts that exact synthetic value or `null`. It is
checked only by HTTP. Never supply a real token. The queues are per tool: each
accepted `tools/call` consumes the next MCP CallToolResult. Script API errors with
`isError: true`; script truncated data with incomplete text in `content`.
Exhaustion returns JSON-RPC error `-32001`; an unknown tool returns `-32602`.
Tool names and catalogs are fixture data, so later scenarios can supply
`testops_*`, `redmine_*`, and `kaiten_*` tools without changing the server.

The JSONL journal records method, tool, sanitized arguments, result category,
and a `write_count` on scripted tool calls. It omits headers and result payloads.
`write_count` counts scripted `write_item` calls only; count journal tool events
for custom write names. Annotation hints do not enforce client policy.

```text
uv run --with pytest pytest tests/integration/test_fake_mcp.py -q
```

## Isolated profile and installation

1. Record `codex --version`, OS/architecture, `codex plugin --help`,
   `codex plugin marketplace add --help`, and `codex plugin add --help`.
   Locate a working executable explicitly if the PATH wrapper is broken.
2. Create a temporary directory containing separate `home/`, `codex/`, `work/`,
   and `market/` directories. Launch all probe commands with a minimal environment
   whose `HOME` and `CODEX_HOME` point inside that directory. Give it only the
   executable PATH and temporary directory it needs. Do not copy credentials,
   use the current user's config, or point it at an existing app-server daemon.
3. Put the fixture server, fixture JSON and a minimal root `plugin.json` in
   `market/plugins/safe-probe/`. The portable manifest is:

   ```json
   {
     "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
     "name": "safe-probe",
     "version": "1.0.0",
     "description": "Synthetic local MCP probe"
   }
   ```

4. Put this catalog at `market/.agents/plugins/marketplace.json`:

   ```json
   {
     "name": "qaily-probe",
     "plugins": [{
       "name": "safe-probe",
       "source": {"source": "local", "path": "./plugins/safe-probe"},
       "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
       "category": "Productivity"
     }]
   }
   ```

5. Inside the isolated environment run:

   ```text
   codex plugin marketplace add PATH_TO_MARKET --json
   codex plugin add safe-probe@qaily-probe --json
   codex plugin list --json
   ```

   Save `installedPath`; inspect and test that cached copy. Also test an
   explicitly chosen synthetic Git marketplace through the Git source form
   advertised by this CLI's help. A local installation does not prove Git
   installation or update behavior. No real qaily marketplace needs installing.

## Transport, helper and policy checks

For portable stdio, use root `mcp.json` with schema
`https://agent-plugins.org/schemas/1.0.0/mcp.schema.json`, a named `mcpServers`
entry with `type: "stdio"`, `command: "python3"`, and arguments pointing to
`${PLUGIN_ROOT}/fake_mcp.py` and `${PLUGIN_ROOT}/fixture.json`. Give the journal
an absolute path inside the temporary profile. The tested CLI requires a bare
executable or a contained `./` command path; an absolute executable is rejected.

For HTTP, start the fixture with synthetic authorization required. Declare a
`type: "streamable-http"` server using its readiness URL. A synthetic helper
must print a JSON header object with `Authorization: Api-Token fixture-value`.
Write a separate marker file when the helper runs; never print helper stdout as
diagnostic evidence. Test these candidates independently, restarting the client:

- Portable server-level `http_headers_helper`.
- The same portable server with plugin-scoped config `http_headers_helper`.
- An OpenAI server extension containing that helper field.
- Root `extensions.com.openai.mcpServers` pointing to a compatibility MCP file.
- Compatibility `.codex-plugin/plugin.json` with `mcpServers: "./.mcp.json"`,
  whose named HTTP server has `url` and `http_headers_helper`.

Keep exactly one registration active. Do not add a top-level `mcp_servers`
connection alongside a plugin server to disguise a failed override. Check the
runtime's exact server name and `pluginId`, not a guessed Claude namespace.
Try `${CLAUDE_PLUGIN_ROOT}` in the compatibility helper and verify it runs from
the freshly installed cache, rather than the source checkout.

Probe policy on that same server:

```toml
[plugins."safe-probe@qaily-probe".mcp_servers.http]
enabled_tools = ["read_item"]
default_tools_approval_mode = "prompt"

[plugins."safe-probe@qaily-probe".mcp_servers.http.tools.read_item]
approval_mode = "approve"
```

Verify that the catalog actually contains only `read_item`. Then allow both
tools for the interactive approval scenario, keeping the default prompt and the
read exception. Also test an innocuous URL override to another loopback fixture;
header helper, effective URL and policy must govern the same connection.

A real `codex app-server --strict-config` can inspect the installed runtime
without a model turn. Generate its exact JSON schemas first:

```text
codex app-server generate-json-schema --experimental --out SCHEMA_DIR
```

Use the schema-described `initialize`/`initialized`, `thread/start`,
`mcpServerStatus/list` and `mcpServer/tool/call` requests. The last method can
check a safe read and its journal entry; a direct app-server tool call is not an
approval-policy test. Do not fabricate an approval client or invoke a write via
this inspection API to claim that approval enforcement works.

## Interactive gate

Use a real interactive Codex client with the isolated profile and approved
client authentication. Stop and mark this portion **not checked** if that
profile cannot run a model turn; do not import or print existing tokens.

1. Ask for one `read_item`. Confirm one successful `tools/call` journal event
   without an extra approval question.
2. Ask for `write_item`; confirm a fresh approval prompt. Reject it and verify
   no `write_item` reaches the journal. Repeat with a second call to ensure
   an earlier approval does not grant permanent write access.
3. Ask the client to delegate the same write request to an isolated subagent.
   Reject the resulting approval; confirm no write event and that the parent
   surfaces the rejection. Do not substitute a simulated subagent.
4. Record the UI actions, actual server and tool IDs, prompt outcome, and
   journal evidence. A missing write event alone does not prove rejection if
   no model ever attempted the tool.

## Tested result and decision rule

On CLI **0.166.0-alpha.5.1**, macOS **26.5.1 arm64**, the local portable package,
installed-cache stdio read, compatibility HTTP helper and same-server tool
allowlist were exercised. The portable HTTP parser rejected helper and extension
fields; the plugin-scoped helper was ignored and HTTP initialization got 401.
Root inline OpenAI MCP delegation yielded no runtime server. Compatibility
`.codex-plugin/plugin.json` + `.mcp.json` is the selected compatibility format following the portable gate failure. The
helper was proven with an absolute synthetic command path. Fresh installed-cache
experiments using either `${CLAUDE_PLUGIN_ROOT}` or `${PLUGIN_ROOT}` inside the
HTTP helper string both exited with status 2 without invoking the helper. A
portable helper-path mechanism is still required before shipping that connection.

Interactive approvals, subagent rejection, Git marketplace installation/update,
URL overrides, Windows/Linux execution and desktop UI remain **not checked**.
Do not claim a minimum supported version from this single tested alpha version.
Do not enable writes until real approval behavior is demonstrated. Packaging can
proceed with the selected compatibility manifest, but HTTP helper path resolution
and URL overrides remain explicit setup gates.

Official platform availability is separate from qaily validation. The current
[desktop guide](https://learn.chatgpt.com/docs/app) lists macOS, Windows and Linux;
the [Linux guide](https://learn.chatgpt.com/docs/linux/linux-app) marks Linux as a
preview for Ubuntu 24.04/26.04, Debian 13, Fedora 43/44 and current Arch, on x64
and ARM64. This does not claim these combinations were tested for qaily.
See also [packaging](https://developers.openai.com/plugins/build/plugins),
[MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), and
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).
