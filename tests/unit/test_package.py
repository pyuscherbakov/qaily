"""Distribution contracts: closed resources, compatible release, pinned servers."""

import json
from pathlib import Path
import re


SKILLS = {
    "test-design", "coverage-gap-design", "review-testcase", "review-autotest",
    "launch-triage", "doctor",
}
SERVERS = {"testops", "redmine", "kaiten", "context7", "playwright", "chrome-devtools", "jam"}


def read_json(root: Path, relative: str) -> dict:
    path = root / relative
    assert path.is_file(), f"missing packaged resource: {relative}"
    return json.loads(path.read_text(encoding="utf-8"))


def contained_resource(root: Path, path: Path) -> None:
    assert path.resolve().is_relative_to(root.resolve()), f"resource escapes package: {path}"
    assert path.exists(), f"unresolved packaged resource: {path.relative_to(root)}"


def test_package_resource_closure(package_copy: Path, monkeypatch, tmp_path: Path) -> None:
    # Break caught: an installed package relies on checkout/cwd or omits a referenced file.
    monkeypatch.chdir(tmp_path)
    for manifest_path in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        manifest = read_json(package_copy, manifest_path)
        contained_resource(package_copy, package_copy / manifest["mcpServers"])
        for resource in ("skills", "agents"):
            paths = manifest.get(resource, f"./{resource}/")
            for relative in paths if isinstance(paths, list) else [paths]:
                contained_resource(package_copy, package_copy / relative)

    marketplace = read_json(package_copy, ".agents/plugins/marketplace.json")
    assert marketplace["name"] == "qaily-codex"
    [plugin] = marketplace["plugins"]
    assert plugin["name"] == "qaily"
    assert plugin["source"]["source"] == "local"
    # Codex resolves source.path from the marketplace root, not this JSON's directory.
    source = (package_copy / plugin["source"]["path"]).resolve()
    contained_resource(package_copy, source / ".codex-plugin/plugin.json")

    assert {path.parent.name for path in (package_copy / "skills").glob("*/SKILL.md")} == SKILLS
    assert {path.stem for path in (package_copy / "agents").glob("*.md")} == {
        "doc-researcher", "autotest-reviewer", "failure-analyst",
    }
    # Core documents must be present in the copied distribution, independent of cwd.
    for relative in (
        "references/platforms/claude.md", "references/platforms/codex.md",
        "references/project-selection.md", "references/projects.json",
        *(f"references/agents/{name}.md" for name in (
            "doc-researcher", "autotest-reviewer", "failure-analyst")),
    ):
        contained_resource(package_copy, package_copy / relative)
    # Resource references include root-relative agent paths and skill-relative ../ paths.
    resource_pattern = re.compile(
        r"(?:\$\{(?:CLAUDE_)?PLUGIN_ROOT\}/)?(?:\.\./)*(?:agents|references|bin|skills)/[\w./-]+\.(?:md|py|json)"
    )
    for directory in ("skills", "agents", "references"):
        for document in (package_copy / directory).rglob("*.md"):
            for match in resource_pattern.finditer(document.read_text(encoding="utf-8")):
                relative = re.sub(r"^\$\{(?:CLAUDE_)?PLUGIN_ROOT\}/", "", match[0])
                base = document.parent if relative.startswith("../") else package_copy
                contained_resource(package_copy, base / relative)
    # Backtick paths may be relative directly to a document (e.g. `projects.json`),
    # which the root-oriented expression above does not cover.
    local_ref = re.compile(r"`((?:(?:\.\./)+|\./)[\w./-]+\.(?:md|json|py)|projects\.json)`")
    for document in (package_copy / "references").rglob("*.md"):
        for relative in local_ref.findall(document.read_text(encoding="utf-8")):
            contained_resource(package_copy, document.parent / relative)
    for config_path in (".mcp.json", "mcp-servers.json"):
        for server in read_json(package_copy, config_path)["mcpServers"].values():
            arguments = server.get("args", [])
            if config_path == ".mcp.json" and "--script" in arguments:
                # Compatibility args are literal; Codex resolves cwd from its cache package.
                script = arguments[arguments.index("--script") + 1]
                directory = package_copy / server.get("cwd", ".")
                contained_resource(package_copy, directory / script)
            for argument in server.get("args", []):
                if "PLUGIN_ROOT}" in argument:
                    relative = argument.split("PLUGIN_ROOT}/", 1)[1]
                    contained_resource(package_copy, package_copy / relative)


def test_manifest_versions_match(package_copy: Path) -> None:
    # Break caught: Codex/Claude install different releases of the shared resources.
    codex = read_json(package_copy, ".codex-plugin/plugin.json")
    claude = read_json(package_copy, ".claude-plugin/plugin.json")
    assert codex["name"] == claude["name"] == "qaily"
    assert codex["version"] == claude["version"] == "0.5.0"


def test_seven_servers_keep_pins(package_copy: Path) -> None:
    # Break caught: packaging drops a connection, changes a dependency or disables the official TestOps connection.
    codex = read_json(package_copy, ".mcp.json")["mcpServers"]
    claude = read_json(package_copy, "mcp-servers.json")["mcpServers"]
    assert set(codex) == set(claude) == SERVERS
    pins = {
        "redmine": "mcp-redmine==2026.09.10.084818",
        "kaiten": "git+https://github.com/pyuscherbakov/kaiten-mcp@8d3c666",
        "context7": "@upstash/context7-mcp@4.1.1",
        "playwright": "@playwright/mcp@0.0.81",
        "chrome-devtools": "chrome-devtools-mcp@1.9.0",
    }
    for servers in (codex, claude):
        for service in ("redmine", "kaiten"):
            args = servers[service]["args"]
            assert args[args.index("--service") + 1] == service
        for name, pin in pins.items():
            assert pin in servers[name]["args"], name
        assert servers["testops"]["url"] == "https://astbroker.qatools.cloud/api/mcp"
        assert servers["jam"]["url"] == "https://mcp.jam.dev/mcp"
    assert codex["testops"]["enabled"] is True
    assert "headersHelper" not in codex["testops"]
    assert "http_headers_helper" not in codex["testops"]


def test_project_catalog_is_display_only_and_complete(package_copy: Path) -> None:
    projects = read_json(package_copy, "references/projects.json")
    assert projects == {
        "1": "FAST2 Автострахование", "36": "FAST2 Виджеты",
        "37": "FAST API Дилеров", "77": "FAST Claims", "34": "FAST Ипотека",
        "42": "Insurplace", "35": "Демо проект", "43": "Копия Автострахование",
        "39": "Кредитный модуль; подпись «= Финансовый модуль»",
        "41": "Лизинг", "76": "Тестирование",
    }


def test_skill_symlink_resolves_resources_from_installed_copy(package_copy: Path, tmp_path: Path) -> None:
    installed_skill = package_copy / "skills/review-testcase"
    link = tmp_path / "external project" / ".agents/skills/review-testcase"
    link.parent.mkdir(parents=True)
    link.symlink_to(installed_skill, target_is_directory=True)
    real_skill = (link / "SKILL.md").resolve()
    for relative in ("../../references/platforms/claude.md", "../../references/platforms/codex.md", "../../references/project-selection.md"):
        contained_resource(package_copy, real_skill.parent / relative)
