"""Policy generation must fail closed when a catalog changes."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin"))


def render_policy(*args, **kwargs):
    import qaily_setup
    return qaily_setup.render_policy(*args, **kwargs)


def parse_fragment(text):
    tomllib = pytest.importorskip('tomllib')
    return tomllib.loads(text)


def effective_server_policy(config, server_id):
    if server_id == 'qaily_testops':
        return config['mcp_servers'][server_id]
    return config['plugins']['qaily@qaily-codex']['mcp_servers'][server_id]


def test_new_tool_never_auto_approved():
    policy = parse_fragment(render_policy(
        {'testops': ['testops_get_case', 'testops_surprise_write']},
        {'testops': ['testops_get_case']}, {'testops': 'qaily_testops'}))
    server = effective_server_policy(policy, 'qaily_testops')
    assert server['default_tools_approval_mode'] == 'prompt'
    assert server['tools']['testops_get_case']['approval_mode'] == 'approve'
    assert server['tools'].get('testops_surprise_write', {}).get('approval_mode') not in {'auto', 'approve'}


def test_kaiten_allowlist_only():
    policy = parse_fragment(render_policy(
        {'kaiten': ['kaiten_get_card', 'kaiten_create_card']},
        {'kaiten': ['kaiten_get_card', 'kaiten_missing']}, {'kaiten': 'kaiten'}))
    assert effective_server_policy(policy, 'kaiten')['enabled_tools'] == ['kaiten_get_card']


def test_absent_catalog_never_enables_guessed_reads():
    policy = parse_fragment(render_policy({}, {'kaiten': ['kaiten_get_card']}, {'kaiten': 'kaiten'}))
    assert effective_server_policy(policy, 'kaiten')['enabled_tools'] == []


def test_policy_uses_actual_server_id():
    policy = parse_fragment(render_policy({'testops': []}, {}, {'testops': 'actual_testops'}, connection_kinds={'testops': 'top-level'}))
    assert policy['mcp_servers']['actual_testops']['default_tools_approval_mode'] == 'prompt'
    assert 'plugins' not in policy


def test_redmine_readonly_is_retained(package_copy: Path):
    config = json.loads((package_copy / '.mcp.json').read_text())
    assert config['mcpServers']['redmine']['env']['REDMINE_READ_ONLY'] == '1'


def test_bundled_testops_policy_targets_plugin_connection():
    policy = parse_fragment(render_policy(
        {'testops': ['read_item']}, {'testops': ['read_item']}, {'testops': 'testops'}))
    server = policy['plugins']['qaily@qaily-codex']['mcp_servers']['testops']
    assert server['default_tools_approval_mode'] == 'prompt'
    assert server['tools']['read_item']['approval_mode'] == 'approve'
    assert 'mcp_servers' not in policy


def test_explicit_kind_handles_renamed_bundled_testops():
    policy = parse_fragment(render_policy(
        {'testops': []}, {}, {'testops': 'renamed'}, connection_kinds={'testops': 'bundled'}))
    assert policy['plugins']['qaily@qaily-codex']['mcp_servers']['renamed']['default_tools_approval_mode'] == 'prompt'


def test_explicit_kind_handles_top_level_named_testops():
    policy = parse_fragment(render_policy(
        {'testops': []}, {}, {'testops': 'testops'}, connection_kinds={'testops': 'top-level'}))
    assert policy['mcp_servers']['testops']['default_tools_approval_mode'] == 'prompt'


def test_unknown_testops_identity_requires_explicit_kind():
    with pytest.raises(ValueError, match='connection kind'):
        render_policy({}, {}, {'testops': 'renamed'})


def test_bundled_servers_start_with_restrictive_policies(package_copy: Path):
    servers = json.loads((package_copy / '.mcp.json').read_text())['mcpServers']
    assert servers['testops']['enabled'] is True
    assert servers['testops']['default_tools_approval_mode'] == 'prompt'
    assert set(servers['kaiten']['enabled_tools']) == {
        'kaiten_get_card', 'kaiten_get_document', 'kaiten_list_comments', 'kaiten_list_documents'}
    assert set(servers['context7']['enabled_tools']) == {'query-docs', 'resolve-library-id'}
    assert servers['jam']['enabled_tools'] == []
