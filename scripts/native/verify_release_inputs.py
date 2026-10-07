#!/usr/bin/env python3
"""Verify checked-in native release downloads without installing or executing them."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import provision  # noqa: E402  pylint: disable=wrong-import-position


MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024


class ReleaseVerificationError(RuntimeError):
    """A declared release input could not be verified."""


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_https_url(url, context, *, allow_query=True):
    if not isinstance(url, str):
        raise ReleaseVerificationError(f'{context}: URL must be a string')
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ReleaseVerificationError(f'{context}: malformed URL') from exc
    if (parsed.scheme != 'https' or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            parsed.fragment or port not in (None, 443) or
            (parsed.query and not allow_query)):
        raise ReleaseVerificationError(
            f'{context}: URL must be credential-free HTTPS on the default port')


def evidence_url(url):
    """Retain the public location without signed or otherwise transient queries."""
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, '', ''))


def evidence_error(exc):
    """Describe failures without retaining redirect URLs or local paths."""
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP download failed with status {exc.code}'
    if isinstance(exc, urllib.error.URLError):
        return 'download transport failed'
    if isinstance(exc, OSError):
        return f'local I/O failed: {exc.strerror or type(exc).__name__}'
    return str(exc)


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirect hops that weaken the declared public HTTPS boundary."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        validate_https_url(new_url, 'download redirect')
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url)


def download_https(url, destination):
    validate_https_url(url, 'declared download', allow_query=False)
    opener = urllib.request.build_opener(HTTPSOnlyRedirectHandler())
    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'budget-analyzer-native-release-verifier/1'},
    )
    with opener.open(request, timeout=120) as response, destination.open('wb') as output:
        final_url = response.geturl()
        validate_https_url(final_url, 'final download')
        declared_size = response.headers.get('Content-Length')
        if declared_size is not None:
            try:
                if int(declared_size) > MAX_DOWNLOAD_BYTES:
                    raise ReleaseVerificationError('download exceeds the size limit')
            except ValueError as exc:
                raise ReleaseVerificationError('malformed download length') from exc
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise ReleaseVerificationError('download exceeds the size limit')
            output.write(chunk)
    if destination.stat().st_size == 0:
        raise ReleaseVerificationError('download is empty')
    return final_url


def safe_archive_name(name, context):
    if not name or '\\' in name or name.startswith('/'):
        raise ReleaseVerificationError(f'{context}: unsafe archive path')
    parts = PurePosixPath(name).parts
    if any(part in ('', '.', '..') for part in parts):
        raise ReleaseVerificationError(f'{context}: unsafe archive path')


def validate_tar_archive(path, tool, arch):
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        if not members:
            raise ReleaseVerificationError('archive is empty')
        names = set()
        for member in members:
            safe_archive_name(member.name, f'{tool["method"]} archive')
            if member.name in names:
                raise ReleaseVerificationError('archive contains duplicate paths')
            names.add(member.name)
            if not (member.isfile() or member.isdir()):
                raise ReleaseVerificationError('archive contains a non-file entry')

        if tool['method'] == 'tar-binary':
            expected = tool['member'].replace('{arch}', arch)
            safe_archive_name(expected, 'declared archive member')
            try:
                member = archive.getmember(expected)
            except KeyError as exc:
                raise ReleaseVerificationError('declared archive member is missing') from exc
            if not member.isfile():
                raise ReleaseVerificationError('declared archive member is not a regular file')
            return expected

        if not all((member.name == 'go' and member.isdir()) or
                   member.name.startswith('go/') for member in members):
            raise ReleaseVerificationError('unexpected Go archive layout')
        if 'go/bin/go' not in names:
            raise ReleaseVerificationError('Go archive executable is missing')
        return 'go/'


def validate_via_archive(path, tool):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos:
            raise ReleaseVerificationError('archive is empty')
        names = set()
        for info in infos:
            safe_archive_name(info.filename.rstrip('/'), 'VIA archive')
            if info.filename in names:
                raise ReleaseVerificationError('archive contains duplicate paths')
            names.add(info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ReleaseVerificationError('archive contains a symbolic link')
            if info.flag_bits & 0x1:
                raise ReleaseVerificationError('archive contains an encrypted member')

        prefix = f'via-{tool["version"]}/'
        required = [prefix + name for name in (
            'via_image_annotator.html', 'LICENSE', 'README.md')]
        if not all(name in names for name in required):
            raise ReleaseVerificationError('VIA archive is missing a required member')
        actual_asset = hashlib.sha256(archive.read(required[0])).hexdigest()
        if actual_asset != tool['asset_sha256']:
            raise ReleaseVerificationError('VIA asset checksum mismatch')
        return prefix


def validate_archive(path, tool, arch):
    method = tool['method']
    if method == 'binary':
        return None
    if method in ('tar-binary', 'go'):
        return validate_tar_archive(path, tool, arch)
    if method == 'via':
        return validate_via_archive(path, tool)
    raise ReleaseVerificationError('unsupported release archive method')


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def load_manifest(path):
    try:
        manifest = provision.load_manifest(path)
    except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError,
            provision.ProvisionError) as exc:
        raise ReleaseVerificationError(f'manifest validation failed: {exc}') from exc
    if not manifest['downloads']:
        raise ReleaseVerificationError('manifest validation failed: no release downloads')
    for name, tool in manifest['downloads'].items():
        if set(tool['platforms']) != set(manifest['architectures']):
            raise ReleaseVerificationError(
                f'manifest validation failed: {name} has an incomplete architecture table')
    return manifest


def verify_release_inputs(manifest_path, output_path, download_dir,
                          downloader=download_https):
    report = {
        'schema': 1,
        'status': 'incomplete',
        'architectures': [],
        'results': [],
        'summary': {'declared': 0, 'verified': 0, 'failed': 0},
    }
    write_report(output_path, report)
    try:
        manifest = load_manifest(manifest_path)
    except ReleaseVerificationError as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        write_report(output_path, report)
        raise

    report['architectures'] = manifest['architectures']
    report['summary']['declared'] = (
        len(manifest['downloads']) * len(manifest['architectures']))
    download_dir.mkdir(parents=True, exist_ok=True)
    write_report(output_path, report)

    for name, tool in manifest['downloads'].items():
        for arch in manifest['architectures']:
            release = tool['platforms'][arch]
            record = {
                'tool': name,
                'architecture': arch,
                'method': tool['method'],
                'status': 'incomplete',
            }
            report['results'].append(record)
            write_report(output_path, report)
            destination = download_dir / f'{name}-{arch}.download'
            try:
                validate_https_url(
                    release['url'], f'{name}/{arch}', allow_query=False)
                destination.unlink(missing_ok=True)
                final_url = downloader(release['url'], destination)
                validate_https_url(final_url, f'{name}/{arch} final URL')
                actual = sha256(destination)
                record.update({
                    'declared_url': release['url'],
                    'final_url': evidence_url(final_url),
                    'expected_sha256': release['sha256'],
                    'actual_sha256': actual,
                    'bytes': destination.stat().st_size,
                })
                if actual != release['sha256']:
                    raise ReleaseVerificationError('checksum mismatch')
                archive_root = validate_archive(destination, tool, arch)
                if archive_root is not None:
                    record['verified_archive_root'] = archive_root
                record['status'] = 'verified'
                report['summary']['verified'] += 1
            except (OSError, ReleaseVerificationError, tarfile.TarError,
                    urllib.error.URLError, zipfile.BadZipFile) as exc:
                record['status'] = 'failed'
                record['error'] = evidence_error(exc)
                report['summary']['failed'] += 1
            write_report(output_path, report)

    report['status'] = (
        'complete' if report['summary']['failed'] == 0 else 'failed')
    write_report(output_path, report)
    if report['status'] != 'complete':
        raise ReleaseVerificationError(
            f'{report["summary"]["failed"]} release input(s) failed verification')
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=provision.MANIFEST)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--download-dir', type=Path, required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        report = verify_release_inputs(
            args.manifest, args.output, args.download_dir)
    except ReleaseVerificationError as exc:
        print(f'release verification failed: {exc}', file=sys.stderr)
        return 1
    print(
        f'verified {report["summary"]["verified"]} release inputs '
        f'for {", ".join(report["architectures"])}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
