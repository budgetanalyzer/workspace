#!/usr/bin/env python3
"""Offline proof that the Claude settings script is an idempotent replace."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'scripts/native/claude_settings.py'
CANONICAL = REPO / 'native/helpers/claude-settings.json'
canonical = json.loads(CANONICAL.read_text())
overlay = json.loads((REPO / 'native/helpers/settings-overlay.json').read_text())


def run(action, path):
    return subprocess.run([sys.executable, str(SCRIPT), action, '--settings-path', str(path)],
                          text=True, capture_output=True)


def backups(path):
    return sorted(path.parent.glob(path.name + '.bak-*'))


def mode(path):
    return path.stat().st_mode & 0o777


assert 'hooks' not in canonical
for key in ('promptSuggestionEnabled', 'autoCompactEnabled'):
    assert canonical[key] == overlay[key], f'{key} differs from overlay'

spec = importlib.util.spec_from_file_location('user_tools', REPO / 'scripts/native/user_tools.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
assert u.merge_settings(canonical, overlay) == canonical

scratch = REPO / 'tmp/native-user-tools'
scratch.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='claude-settings-', dir=scratch) as name:
    root = Path(name)

    # check: identical, different, invalid.
    target = root / 'check/settings.json'
    target.parent.mkdir()
    target.write_text(json.dumps(canonical))
    assert run('check', target).returncode == 0
    target.write_text(json.dumps({**canonical, 'theme': 'light'}))
    result = run('check', target)
    assert result.returncode == 1 and 'theme' in result.stderr, result.stderr
    target.write_text('{not json')
    assert run('check', target).returncode == 2

    # apply: legacy file with hook and extra keys.
    target = root / 'legacy/settings.json'
    target.parent.mkdir()
    original = json.dumps({**canonical, 'extra': 1, 'hooks': {'SessionStart': [{'hooks': [
        {'type': 'command', 'command': 'cat AGENTS.md'}]}]}})
    target.write_text(original)
    target.chmod(0o644)
    assert run('check', target).returncode == 1
    result = run('apply', target)
    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text()) == canonical
    assert 'hooks' not in json.loads(target.read_text())
    found = backups(target)
    assert len(found) == 1 and found[0].read_text() == original
    assert mode(target) == 0o600 and mode(found[0]) == 0o600
    assert run('check', target).returncode == 0

    # apply again: nothing changes.
    before, stamp = target.read_bytes(), target.stat().st_mtime_ns
    result = run('apply', target)
    assert result.returncode == 0 and 'already up to date' in result.stdout
    assert target.read_bytes() == before and target.stat().st_mtime_ns == stamp
    assert len(backups(target)) == 1
    assert list(target.parent.glob('.settings.json.*')) == []

    # missing target: created, no backup.
    target = root / 'missing/.claude/settings.json'
    result = run('apply', target)
    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text()) == canonical
    assert backups(target) == [] and mode(target) == 0o600

    # symlink target: refused, destination untouched.
    destination = root / 'link/real.json'
    destination.parent.mkdir()
    destination.write_text('{"keep": true}')
    link = root / 'link/settings.json'
    link.symlink_to(destination)
    result = run('apply', link)
    assert result.returncode == 2 and 'symlink' in result.stderr
    assert destination.read_text() == '{"keep": true}' and link.is_symlink()
    assert backups(link) == []
print('claude settings checks passed')
