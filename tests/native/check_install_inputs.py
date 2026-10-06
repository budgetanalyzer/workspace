#!/usr/bin/env python3
"""Validate native npm inputs and their proposed or committed Git closure."""
import argparse
import base64
import binascii
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile


REPO = Path(__file__).resolve().parents[2]
LOCK_PATH = Path('native/npm/package-lock.json')
SETTINGS_PATH = Path('native/helpers/settings-overlay.json')
REQUIRED_INPUTS = (
    Path('native/npm/package.json'),
    LOCK_PATH,
    SETTINGS_PATH,
    Path('native/toolchain.json'),
    Path('scripts/native/user_tools.py'),
)
PROPOSED_NEW_SOURCE = (LOCK_PATH, SETTINGS_PATH)


class InstallInputError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise InstallInputError(message)


def run_git(repo, *args, check=True):
    result = subprocess.run(
        ['git', '-C', str(repo), *map(str, args)],
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise InstallInputError(
            f'git {args[0]} failed with exit {result.returncode}')
    return result


def validate_integrity(value, package):
    require(isinstance(value, str) and value.startswith('sha512-'),
            f'{package}: missing SHA-512 integrity')
    try:
        decoded = base64.b64decode(value.removeprefix('sha512-'), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InstallInputError(f'{package}: malformed SHA-512 integrity') from exc
    require(len(decoded) == 64, f'{package}: malformed SHA-512 integrity')


def validate_source(root):
    for relative in REQUIRED_INPUTS:
        require((root / relative).is_file(), f'missing required install input: {relative}')

    package = json.loads((root / 'native/npm/package.json').read_text())
    lock_path = root / LOCK_PATH
    lock = json.loads(lock_path.read_text())
    manifest = json.loads((root / 'native/toolchain.json').read_text())

    require(lock.get('lockfileVersion') == 3, 'npm lockfileVersion must remain 3')
    require(lock.get('name') == package.get('name') and
            lock.get('version') == package.get('version'),
            'npm manifest and lock package identity mismatch')
    packages = lock.get('packages')
    require(isinstance(packages, dict) and isinstance(packages.get(''), dict),
            'npm lock packages map/root entry missing')
    require(packages[''].get('dependencies') == package.get('dependencies'),
            'npm manifest and lock direct dependencies mismatch')
    require(manifest.get('reviewed_sources', {}).get('npm_lock') == str(LOCK_PATH),
            'toolchain npm lock source path mismatch')
    require(manifest.get('reviewed_sources', {}).get('settings') == str(SETTINGS_PATH),
            'toolchain settings source path mismatch')
    settings = json.loads((root / SETTINGS_PATH).read_text())
    require(settings.get('hooks', {}).get('SessionStart'),
            'managed SessionStart settings hook missing')

    npm_tools = {
        name: tool for name, tool in manifest.get('user_tools', {}).items()
        if tool.get('method') == 'npm'
    }
    expected_dependencies = {
        name: tool['version'] for name, tool in npm_tools.items()
    }
    require(package.get('dependencies') == expected_dependencies,
            'npm manifest and toolchain direct versions mismatch')
    for name, tool in npm_tools.items():
        entry = packages.get(f'node_modules/{name}')
        require(isinstance(entry, dict), f'locked direct dependency missing: {name}')
        require(entry.get('version') == tool.get('version'),
                f'{name}: reviewed version mismatch')
        require(entry.get('resolved') == tool.get('tarball'),
                f'{name}: reviewed tarball mismatch')
        require(entry.get('integrity') == tool.get('integrity'),
                f'{name}: reviewed integrity mismatch')

    for package_path, entry in packages.items():
        if not package_path:
            continue
        parts = PurePosixPath(package_path).parts
        require(parts and parts[0] == 'node_modules' and '..' not in parts,
                f'unsafe npm package path: {package_path}')
        require(isinstance(entry, dict) and isinstance(entry.get('version'), str),
                f'{package_path}: locked version missing')
        resolved = entry.get('resolved')
        require(isinstance(resolved, str) and
                resolved.startswith('https://registry.npmjs.org/'),
                f'{package_path}: registry HTTPS tarball missing')
        validate_integrity(entry.get('integrity'), package_path)

    return hashlib.sha256(lock_path.read_bytes()).hexdigest(), len(packages) - 1


def git_input_state(repo, relative):
    ignored = run_git(repo, 'check-ignore', '--quiet', '--', relative, check=False)
    require(ignored.returncode in (0, 1),
            f'could not evaluate ignore policy for {relative}')
    require(ignored.returncode == 1, f'required install input is ignored: {relative}')
    tracked = run_git(
        repo, 'ls-files', '--error-unmatch', '--', relative, check=False)
    require(tracked.returncode in (0, 1),
            f'could not evaluate publication state for {relative}')
    return tracked.returncode == 0


def validate_repository_policy(repo, publication):
    states = {path: git_input_state(repo, path) for path in REQUIRED_INPUTS}
    for path, tracked in states.items():
        if not tracked:
            require(publication == 'proposed' and path in PROPOSED_NEW_SOURCE,
                    f'required install input is not committed: {path}')
    return states


def copy_proposed_source(repo, destination):
    tracked = run_git(repo, 'ls-files', '-z').stdout.split(b'\0')
    for raw in tracked:
        if not raw:
            continue
        relative = Path(raw.decode())
        source = repo / relative
        if not source.exists():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(source.readlink())
        else:
            shutil.copy2(source, target)
    for relative in PROPOSED_NEW_SOURCE:
        source = repo / relative
        if not (destination / relative).exists():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def export_committed_source(repo, destination):
    archive = run_git(repo, 'archive', '--format=tar', 'HEAD').stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as stream:
        stream.extractall(destination, filter='data')


def validate_export(repo, publication):
    scratch = repo / 'tmp/native-install-input-source'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'{publication}-', dir=scratch) as name:
        exported = Path(name)
        if publication == 'proposed':
            copy_proposed_source(repo, exported)
        else:
            export_committed_source(repo, exported)
        require(not (exported / '.git').exists(), 'source export unexpectedly contains Git state')
        return validate_source(exported)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--publication', choices=('proposed', 'committed'), default='proposed',
        help='proposed copies tracked working-tree source plus reviewed new inputs; '
             'committed validates a true git archive HEAD export',
    )
    args = parser.parse_args()
    try:
        states = validate_repository_policy(REPO, args.publication)
        lock_hash, package_count = validate_source(REPO)
        export_hash, export_package_count = validate_export(REPO, args.publication)
        require((lock_hash, package_count) == (export_hash, export_package_count),
                'source export npm inputs differ from reviewed working source')
    except (InstallInputError, OSError, json.JSONDecodeError, KeyError,
            tarfile.TarError) as exc:
        print(f'native-install-inputs: {exc}', file=sys.stderr)
        return 1

    pending = [str(path) for path, tracked in states.items() if not tracked]
    proof = ('tracked working-tree source plus explicit reviewed new source'
             if args.publication == 'proposed' else 'git archive HEAD')
    status = (f'; publication pending for {", ".join(pending)}'
              if pending else '; all required inputs committed')
    print(f'Native install inputs PASS: {package_count} locked packages; '
          f'lock SHA-256 {lock_hash}; source-only proof: {proof}{status}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
