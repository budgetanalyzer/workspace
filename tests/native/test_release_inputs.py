"""Offline tests for native public-release input verification."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
SCRATCH = REPO / 'tmp'
SPEC = importlib.util.spec_from_file_location(
    'verify_release_inputs', REPO / 'scripts/native/verify_release_inputs.py')
release_inputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_inputs)


def tar_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, body in entries:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return stream.getvalue()


class ReleaseInputTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix='release-inputs-', dir=SCRATCH)
        self.root = Path(self.temporary.name)
        self.output = self.root / 'evidence/release-verification.json'
        self.downloads = self.root / 'downloads'

        self.binary = b'fixture binary; never execute\n'
        self.archive = tar_bytes([
            ('linux-amd64/tool-archive', b'amd64 fixture\n'),
            ('linux-arm64/tool-archive', b'arm64 fixture\n'),
        ])
        self.assets = {
            'https://fixtures.example/releases/1.2.3/tool-binary-amd64': self.binary,
            'https://fixtures.example/releases/1.2.3/tool-binary-arm64': self.binary,
            'https://fixtures.example/releases/1.2.3/tool-archive-amd64.tar.gz': self.archive,
            'https://fixtures.example/releases/1.2.3/tool-archive-arm64.tar.gz': self.archive,
        }
        self.manifest = json.loads(
            (REPO / 'native/toolchain.json').read_text())
        self.manifest['downloads'] = {
            'tool-binary': self.tool('binary', self.binary),
            'tool-archive': self.tool(
                'tar-binary', self.archive, member='linux-{arch}/tool-archive'),
        }
        self.write_manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def tool(self, method, body, **extra):
        name = 'tool-binary' if method == 'binary' else 'tool-archive'
        suffix = '' if method == 'binary' else '.tar.gz'
        digest = hashlib.sha256(body).hexdigest()
        tool = {
            'owner': 'system',
            'version': '1.2.3',
            'policy': 'explicit-reviewed-refresh',
            'method': method,
            'destination': f'/usr/local/bin/{name}',
            'platforms': {
                arch: {
                    'url': f'https://fixtures.example/releases/1.2.3/{name}-{arch}{suffix}',
                    'sha256': digest,
                } for arch in ('amd64', 'arm64')
            },
            'check': [name, '--version'],
            'version_pattern': r'(?<![0-9.])1\.2\.3(?![0-9.])',
        }
        tool.update(extra)
        return tool

    def write_manifest(self, value=None):
        self.manifest_path = self.root / 'toolchain.json'
        self.manifest_path.write_text(json.dumps(
            self.manifest if value is None else value))

    def downloader(self, url, destination):
        destination.write_bytes(self.assets[url])
        return url

    def verify(self, downloader=None):
        return release_inputs.verify_release_inputs(
            self.manifest_path,
            self.output,
            self.downloads,
            downloader=downloader or self.downloader,
        )

    def report(self):
        return json.loads(self.output.read_text())

    def test_success_verifies_both_architectures_without_execution(self):
        report = self.verify()
        self.assertEqual('complete', report['status'])
        self.assertEqual({'amd64', 'arm64'}, set(report['architectures']))
        self.assertEqual(4, report['summary']['verified'])
        self.assertTrue(all(
            result['status'] == 'verified' for result in report['results']))

    def test_checksum_mismatch_is_rejected(self):
        self.manifest['downloads']['tool-binary']['platforms']['arm64'][
            'sha256'] = '0' * 64
        self.write_manifest()
        with self.assertRaisesRegex(
                release_inputs.ReleaseVerificationError,
                '1 release input'):
            self.verify()
        failed = [item for item in self.report()['results']
                  if item['status'] == 'failed']
        self.assertEqual('checksum mismatch', failed[0]['error'])

    def test_unsafe_archive_layout_is_rejected(self):
        unsafe = tar_bytes([
            ('linux-amd64/tool-archive', b'fixture\n'),
            ('../escape', b'unsafe\n'),
        ])
        for arch in ('amd64', 'arm64'):
            url = self.manifest['downloads']['tool-archive']['platforms'][arch]['url']
            self.assets[url] = unsafe
            self.manifest['downloads']['tool-archive']['platforms'][arch][
                'sha256'] = hashlib.sha256(unsafe).hexdigest()
        self.write_manifest()
        with self.assertRaises(release_inputs.ReleaseVerificationError):
            self.verify()
        failures = [item for item in self.report()['results']
                    if item['status'] == 'failed']
        self.assertEqual(2, len(failures))
        self.assertTrue(all('unsafe archive path' in item['error']
                            for item in failures))

    def test_absent_architecture_is_rejected_before_download(self):
        del self.manifest['downloads']['tool-binary']['platforms']['arm64']
        self.write_manifest()
        with self.assertRaisesRegex(
                release_inputs.ReleaseVerificationError,
                'manifest validation failed'):
            self.verify()
        report = self.report()
        self.assertEqual('failed', report['status'])
        self.assertEqual([], report['results'])

    def test_malformed_manifest_leaves_failure_evidence(self):
        self.write_manifest({'schema': 1})
        with self.assertRaisesRegex(
                release_inputs.ReleaseVerificationError,
                'manifest validation failed'):
            self.verify()
        report = self.report()
        self.assertEqual('failed', report['status'])
        self.assertIn('error', report)

    def test_partial_evidence_survives_download_failure(self):
        calls = []

        def partially_failing_download(url, destination):
            calls.append(url)
            if url.endswith('tool-archive-amd64.tar.gz'):
                raise OSError('mocked unavailable release')
            return self.downloader(url, destination)

        with self.assertRaises(release_inputs.ReleaseVerificationError):
            self.verify(partially_failing_download)
        report = self.report()
        self.assertEqual(4, len(calls))
        self.assertEqual(3, report['summary']['verified'])
        self.assertEqual(1, report['summary']['failed'])
        self.assertEqual('failed', report['status'])

    def test_unsafe_redirect_is_rejected(self):
        def redirected_download(url, destination):
            destination.write_bytes(self.assets[url])
            return 'http://fixtures.example/unsafe'

        with self.assertRaises(release_inputs.ReleaseVerificationError):
            self.verify(redirected_download)
        self.assertEqual(4, self.report()['summary']['failed'])

    def test_signed_redirect_query_is_not_retained(self):
        def signed_redirect_download(url, destination):
            destination.write_bytes(self.assets[url])
            return url + '?signature=temporary-secret'

        report = self.verify(signed_redirect_download)
        self.assertTrue(all('?' not in item['final_url']
                            for item in report['results']))


if __name__ == '__main__':
    unittest.main()
