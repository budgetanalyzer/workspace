#!/usr/bin/env python3
"""Offline verifier for native/helpers/statusline-command.sh."""
import json
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'native' / 'helpers' / 'statusline-command.sh'
(REPO / 'tmp').mkdir(exist_ok=True)
BLUE, RESET = '\033[01;34m', '\033[00m'
MARGIN = 30

with tempfile.TemporaryDirectory(dir=REPO / 'tmp') as home:
    def run(payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        result = subprocess.run(['bash', str(SCRIPT)], input=text, text=True, capture_output=True,
                                env={'PATH': '/usr/bin:/bin', 'HOME': home, 'TZ': 'UTC'})
        assert result.returncode == 0, result.stderr
        assert result.stderr == '', result.stderr
        return result.stdout

    def iso(epoch, fraction=False, zone='Z'):
        stamp = datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        return stamp + ('.250' if fraction else '') + zone

    def at(offset):
        return int(time.time()) + offset + MARGIN

    def payload(five=None, week=None, ctx=42, directory=f'{home}/dir', **extra):
        data = {'workspace': {'current_dir': directory}, 'model': {'display_name': 'Opus 5.5'},
                'context_window': {'used_percentage': ctx},
                'rate_limits': {'five_hour': five, 'seven_day': week}}
        data.update(extra)
        return data

    five_offset = 2 * 3600 + 13 * 60
    week_offset = 3 * 86400 + 4 * 3600

    # full line
    out = run(payload({'used_percentage': 31, 'resets_at': at(five_offset)},
                      {'used_percentage': 12, 'resets_at': at(week_offset)}))
    assert out == f'{BLUE}~/dir{RESET} | Opus 5.5 | ctx 42% | 5h 31% (2h13m) | 7d 12% (3d4h)\n', repr(out)
    assert '@' not in out
    assert set(re.findall(r'\033\[[0-9;]*m', out)) == {BLUE, RESET}

    # rounding and utilization fallback
    out = run(payload({'utilization': 30.5, 'resets_at': at(600)}, ctx=41.6))
    assert 'ctx 42%' in out and '5h 31% (' in out, out

    # reset formats agree
    expected = '5h 31% (2h13m)'
    target = at(five_offset)
    for value in (target, target * 1000, iso(target), iso(target, True), iso(target, zone='+00:00'),
                  iso(target, True, '+00:00')):
        out = run(payload({'used_percentage': 31, 'resets_at': value}))
        assert expected in out, (value, out)

    # past reset and short durations
    assert '5h 31% (now)' in run(payload({'used_percentage': 31, 'resets_at': int(time.time()) - 100}))
    assert '5h 31% (7m)' in run(payload({'used_percentage': 31, 'resets_at': at(7 * 60)}))

    # omitted segments
    out = run(payload(None, None))
    assert out == f'{BLUE}~/dir{RESET} | Opus 5.5 | ctx 42%\n', repr(out)
    assert run(payload(rate_limits=None)) == out
    out = run(payload(ctx=None))
    assert 'ctx' not in out
    out = run(payload({'used_percentage': 31}, {'used_percentage': 9, 'resets_at': 'garbage'}))
    assert out.endswith('5h 31% | 7d 9%\n'), repr(out)

    # directories
    assert f'{BLUE}/srv/other{RESET}' in run(payload(directory='/srv/other'))
    assert f'{BLUE}~{RESET}' in run(payload(directory=home))
    assert f'{BLUE}{home}x{RESET}' in run(payload(directory=f'{home}x'))
    data = payload()
    del data['workspace']
    data['cwd'] = '/srv/cwd'
    assert f'{BLUE}/srv/cwd{RESET}' in run(data)
    assert f'{BLUE}/tmp/100%\\n{RESET}' in run(payload(directory='/tmp/100%\\n'))

    # empty and invalid input
    for bad in ('', '\n', 'not json', '{', '[]', '{}', 'null'):
        assert run(bad) == '', bad

text = SCRIPT.read_text()
for banned in ('curl', 'wget', '.credentials', 'mktemp'):
    assert banned not in text, banned
assert not re.search(r'>>?\s*(?!/dev/null|&)[^\s]', text.replace('2>/dev/null', '')), 'file redirection'
assert SCRIPT.stat().st_mode & 0o111

print('statusline checks passed')
