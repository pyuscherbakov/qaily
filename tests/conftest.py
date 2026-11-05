"""Copies of distributable resources, independent of the checkout and its cwd."""

from pathlib import Path
import shutil

import pytest

# These are source examples read by review-autotest, not tests of this package.
collect_ignore = ["fixtures/autotests"]


@pytest.fixture
def package_copy(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "Qaily пакет с пробелами"
    target.mkdir()
    for relative in (
        ".codex-plugin", ".claude-plugin", ".agents/plugins", ".mcp.json",
        "mcp-servers.json", "skills", "agents", "references",
        "bin/qaily_launch.py", "bin/qaily_diagnostics.py", "bin/qaily_config.py", "bin/qaily_setup.py", "README.md", "docs/codex-install.md",
        "docs/windows-checklist.md", "settings.local.json.example",
    ):
        path = source / relative
        if not path.exists():
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
    return target
