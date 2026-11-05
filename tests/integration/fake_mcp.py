#!/usr/bin/env python3
"""Loopback-only scripted MCP fixture. Never use real credentials or service data.

HTTP prints one readiness JSON line with its URL; stdio is newline-delimited JSON-RPC.
Each process truncates its journal and owns independent response queues.
"""
from __future__ import annotations

import argparse
from collections import deque
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import sys


_SECRET_KEY = re.compile(r"authorization|token|secret|password|api[_-]?key|cookie", re.I)


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {key: "[redacted]" if _SECRET_KEY.search(str(key)) else _redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return value.replace("fixture-value", "[redacted]")
    return value


def record_event(path: Path, event: dict[str, object]) -> None:
    """Append only approved diagnostic fields; omit headers and result payloads."""
    fields = ("method", "tool", "arguments", "result_category", "write_count")
    safe = {key: _redact(event[key]) for key in fields if key in event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(safe, ensure_ascii=False) + "\n")


class FixtureServer:
    def __init__(self, fixture: dict, journal: Path):
        self.tools = fixture["tools"]
        self.responses = {name: deque(items) for name, items in fixture["responses"].items()}
        self.authorization = fixture.get("required_authorization")
        if self.authorization not in (None, "Api-Token fixture-value"):
            raise ValueError("only synthetic fixture authorization is accepted")
        self.journal = journal
        self.journal.write_text("", encoding="utf-8")
        self.write_count = 0

    def handle(self, message: dict) -> dict | None:
        method = message.get("method")
        event: dict[str, object] = {"method": method, "result_category": "success"}
        result = None
        error = None
        params = message.get("params", {})
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-03-26"),
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "qaily-fixture", "version": "1.0.0"}}
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            result = {"tools": self.tools}
        elif method == "tools/call":
            name = params.get("name")
            event.update(tool=name, arguments=params.get("arguments", {}))
            if name not in {tool["name"] for tool in self.tools}:
                error = {"code": -32602, "message": "Unknown fixture tool"}
                event["result_category"] = "invalid_params"
            elif not self.responses.get(name):
                error = {"code": -32001, "message": "Fixture response queue exhausted"}
                event["result_category"] = "fixture_exhausted"
            else:
                result = self.responses[name].popleft()
                event["result_category"] = "tool_error" if result.get("isError") else "success"
                if name == "write_item":
                    self.write_count += 1
                event["write_count"] = self.write_count
        elif method == "ping":
            result = {}
        else:
            error = {"code": -32601, "message": "Method not found"}
            event["result_category"] = "method_not_found"
        record_event(self.journal, event)
        if "id" not in message:
            return None
        response = {"jsonrpc": "2.0", "id": message["id"]}
        response["error" if error else "result"] = error if error else result
        return response


def serve_http(fixture: FixtureServer, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # No request headers or payloads in stderr/access logs.

        def do_POST(self):
            if fixture.authorization and self.headers.get("Authorization") != fixture.authorization:
                self.send_response(401)
                self.end_headers()
                return
            try:
                message = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                response = fixture.handle(message)
            except (ValueError, TypeError, AttributeError):
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "Invalid JSON-RPC request"}}
            payload = json.dumps(response).encode() if response is not None else b""
            self.send_response(200 if payload else 202)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.send_response(405)  # Stateless transport has no unsolicited event stream.
            self.end_headers()

    with HTTPServer((host, port), Handler) as server:
        print(json.dumps({"url": f"http://{host}:{server.server_port}/mcp"}), flush=True)
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", required=True, choices=("stdio", "http"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not ipaddress.ip_address(args.host).is_loopback or ":" in args.host:
            parser.error("host must be an IPv4 loopback address")
    except ValueError:
        parser.error("host must be a numeric IPv4 loopback address")
    try:
        fixture = FixtureServer(json.loads(args.fixture.read_text(encoding="utf-8")), args.journal)
    except (ValueError, KeyError, TypeError):
        parser.error("invalid synthetic fixture")
    if args.transport == "http":
        serve_http(fixture, args.host, args.port)
    else:
        for line in sys.stdin.buffer:
            response = fixture.handle(json.loads(line))
            if response is not None:
                sys.stdout.buffer.write(json.dumps(response).encode("utf-8") + b"\n")
                sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
