#!/usr/bin/env python3
"""Human-run, idempotent replacement of Claude user settings from a reviewed file."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

CANONICAL = Path(__file__).resolve().parents[2] / 'native/helpers/claude-settings.json'
DEFAULT_TARGET = Path.home() / '.claude/settings.json'


class SettingsError(Exception):
    pass


def require(ok, message):
    if not ok:
        raise SettingsError(message)


def load_json(path, label):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise SettingsError(f'{label}: unreadable or invalid JSON ({type(error).__name__})')


def check_target(path):
    """Return True when the target exists; refuse symlinks and non-regular files."""
    if not os.path.lexists(path):
        return False
    status = os.lstat(path)
    require(not stat.S_ISLNK(status.st_mode), f'refusing symlink target: {path}')
    require(stat.S_ISREG(status.st_mode), f'refusing non-regular target: {path}')
    return True


def differences(current, desired):
    if not isinstance(current, dict):
        return ['<top level>: not a JSON object']
    result = []
    for key in sorted(set(current) | set(desired)):
        if key not in current:
            result.append(f'{key}: missing')
        elif key not in desired:
            result.append(f'{key}: unexpected')
        elif current[key] != desired[key]:
            result.append(f'{key}: differs')
    return result


def check(path):
    desired = load_json(CANONICAL, 'canonical settings')
    if not check_target(path):
        print(f'{path}: missing', file=sys.stderr)
        return 1
    found = differences(load_json(path, str(path)), desired)
    if found:
        print('settings differ:\n  ' + '\n  '.join(found), file=sys.stderr)
        return 1
    print('settings match canonical')
    return 0


def apply(path):
    desired = load_json(CANONICAL, 'canonical settings')
    exists = check_target(path)
    if exists:
        current = load_json(path, str(path))
        if not differences(current, desired):
            print('already up to date')
            return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        backup = path.with_name(f'{path.name}.bak-{time.strftime("%Y%m%dT%H%M%S")}')
        require(not os.path.lexists(backup), f'backup already exists: {backup}')
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(path.read_bytes())
    fd, temp = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(desired, handle, indent=2)
            handle.write('\n')
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        if os.path.lexists(temp):
            os.unlink(temp)
        raise
    print(f'settings replaced: {path}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'apply'))
    parser.add_argument('--settings-path', type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    try:
        return (check if args.action == 'check' else apply)(args.settings_path)
    except SettingsError as error:
        print(f'claude_settings: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
