"""Real subprocess checks: transport, authorization, scripted errors and safe journals."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import threading
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

SERVER = Path(__file__).with_name("fake_mcp.py")


def text_result(text, **extra):
    return {"content": [{"type": "text", "text": text}], **extra}


def fixture_data():
    return {
        "tools": [
            {"name": name, "description": name, "inputSchema": {"type": "object"},
             "annotations": {"readOnlyHint": name == "read_item"}}
            for name in ("read_item", "write_item")
        ],
        "responses": {
            "read_item": [text_result("first"), text_result("api failed", isError=True),
                          text_result('{"cut":')],
            "write_item": [text_result("written")],
        },
        "required_authorization": "Api-Token fixture-value",
    }


def read_line(process):
    output = queue.Queue()
    threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
    try:
        line = output.get(timeout=5)
    except queue.Empty:
        pytest.fail("fixture server did not respond within 5 seconds")
    assert line, "fixture server exited: " + process.stderr.read().decode()
    return json.loads(line)


@contextlib.contextmanager
def server(tmp_path, transport, data=None, host="127.0.0.1"):
    fixture = tmp_path / "fixture.json"
    journal = tmp_path / "journal.jsonl"
    fixture.write_text(json.dumps(data or fixture_data()))
    with subprocess.Popen(
        [sys.executable, str(SERVER), "--transport", transport, "--host", host,
         "--port", "0", "--journal", str(journal), "--fixture", str(fixture)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ) as process:
        try:
            url = read_line(process)["url"] if transport == "http" else None

            def request(method, params=None, *, auth="Api-Token fixture-value", notify=False):
                message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
                if not notify:
                    message["id"] = 1
                body = json.dumps(message).encode() + b"\n"
                if transport == "stdio":
                    process.stdin.write(body)
                    process.stdin.flush()
                    return None if notify else read_line(process)
                headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
                if auth is not None:
                    headers["Authorization"] = auth
                with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=5) as response:
                    payload = response.read()
                    return json.loads(payload) if payload else None

            yield request, journal
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_fake_mcp_protocol_and_auth(tmp_path, transport):
    # A missing auth guard, eager write, or transport-only implementation breaks this.
    with server(tmp_path, transport) as (request, journal):
        if transport == "http":
            for auth in (None, "Api-Token wrong"):
                with pytest.raises(urllib.error.HTTPError) as error:
                    request("initialize", auth=auth)
                assert error.value.code == 401
        result = request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "1"}})
        assert result["result"]["protocolVersion"] == "2025-03-26"
        assert result["result"]["capabilities"] == {"tools": {}}
        request("notifications/initialized", notify=True)
        tools = request("tools/list")["result"]["tools"]
        assert [tool["name"] for tool in tools] == ["read_item", "write_item"]
        assert tools[0]["annotations"]["readOnlyHint"] is True
        assert not any(event.get("tool") == "write_item" for event in events(journal))
        assert request("tools/call", {"name": "read_item", "arguments": {"id": 7}})["result"] == text_result("first")
        if transport == "http":
            with pytest.raises(urllib.error.HTTPError):
                request("tools/call", {"name": "write_item"}, auth=None)
            assert not any(event.get("tool") == "write_item" for event in events(journal))
        assert request("tools/call", {"name": "write_item", "arguments": {"id": 7}})["result"] == text_result("written")
        writes = [event for event in events(journal) if event.get("tool") == "write_item"]
        assert len(writes) == 1
        assert writes[0]["write_count"] == 1
        assert writes[0]["arguments"] == {"id": 7}
        assert "fixture-value" not in journal.read_text()
        assert "Authorization" not in journal.read_text()


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_scripted_errors_truncation_and_exhaustion(tmp_path, transport):
    # Reusing a response, swallowing isError, or fabricating truncated text breaks this.
    with server(tmp_path, transport) as (request, journal):
        assert request("tools/call", {"name": "read_item"})["result"] == text_result("first")
        assert request("tools/call", {"name": "read_item"})["result"] == text_result("api failed", isError=True)
        assert request("tools/call", {"name": "read_item"})["result"] == text_result('{"cut":')
        exhausted = request("tools/call", {"name": "read_item"})
        assert exhausted["error"]["code"] == -32001
        assert "exhausted" in exhausted["error"]["message"].lower()
        unknown = request("tools/call", {"name": "not_a_tool"})
        assert unknown["error"]["code"] == -32602
        assert [event["result_category"] for event in events(journal)] == [
            "success", "tool_error", "success", "fixture_exhausted", "invalid_params"]


def test_custom_catalog_and_fresh_journal(tmp_path):
    # Hardcoding the two probe tool names or appending old sessions breaks this.
    data = fixture_data()
    data["tools"][0]["name"] = "testops_get_case"
    data["responses"]["testops_get_case"] = [text_result("case 1")]
    journal = tmp_path / "journal.jsonl"
    journal.write_text('old-session\n')
    with server(tmp_path, "stdio", data) as (request, journal):
        assert request("tools/list")["result"]["tools"][0]["name"] == "testops_get_case"
        assert request("tools/call", {"name": "testops_get_case"})["result"] == text_result("case 1")
        assert "old-session" not in journal.read_text()


def test_record_event_does_not_log_credentials(tmp_path):
    # Logging arbitrary events or nested credential values without redaction breaks this.
    assert SERVER.exists(), "fixture MCP server must exist"
    spec = importlib.util.spec_from_file_location("fake_mcp", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    journal = tmp_path / "journal.jsonl"
    module.record_event(journal, {
        "method": "tools/call", "tool": "read_item", "result_category": "success",
        "headers": {"Authorization": "Api-Token fixture-value"},
        "arguments": {"id": 7, "token": "private-token", "nested": {"api_key": "private-key"},
                      "text": "Api-Token fixture-value"},
        "result": {"secret": "private-result"},
    })
    raw = journal.read_text()
    assert all(secret not in raw for secret in ("fixture-value", "private-token", "private-key", "private-result", "Authorization"))
    assert events(journal)[0]["arguments"]["id"] == 7


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1"])
def test_rejects_non_loopback_bind(tmp_path, host):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(fixture_data()))
    result = subprocess.run([sys.executable, str(SERVER), "--transport", "http", "--host", host,
                             "--port", "0", "--journal", str(tmp_path / "log"),
                             "--fixture", str(fixture)], capture_output=True, timeout=5)
    assert result.returncode != 0
    assert b"loopback" in result.stderr.lower()


def test_stdio_preserves_utf8_under_legacy_process_encoding(tmp_path):
    # Platform-decoded stdin corrupts UTF-8 arguments; platform-encoded stdout may
    # corrupt a Unicode result. Check both actual subprocess wire and journal.
    data = fixture_data()
    data["responses"]["read_item"] = [text_result("Ответ: снеговик ☃")]
    fixture = tmp_path / "fixture.json"
    journal = tmp_path / "journal.jsonl"
    fixture.write_text(json.dumps(data), encoding="utf-8")
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "read_item", "arguments": {"text": "Привет"}}}
    result = subprocess.run(
        [sys.executable, str(SERVER), "--transport", "stdio", "--journal", str(journal),
         "--fixture", str(fixture)],
        input=(json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"),
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    response = json.loads(result.stdout.decode("utf-8"))
    assert response["result"] == text_result("Ответ: снеговик ☃")
    event = json.loads(journal.read_text(encoding="utf-8"))
    assert event["arguments"] == {"text": "Привет"}
