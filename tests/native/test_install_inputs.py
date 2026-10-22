"""Focused native install-input closure and publication-policy checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
SCRATCH = REPO / 'tmp/native-installer-safety'
SCRATCH.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location(
    'check_install_inputs', REPO / 'tests/native/check_install_inputs.py')
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


class InstallInputTests(unittest.TestCase):
    def copied_inputs(self, root):
        for relative in inputs.REQUIRED_INPUTS:
            source = REPO / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_reviewed_source_is_complete(self):
        lock_hash, package_count = inputs.validate_source(REPO)
        self.assertEqual(
            'a9a9e5ba0bdb4e13517d28e2b15f74a7a470348f23fdf2dae4df95543d9fd3af',
            lock_hash,
        )
        self.assertEqual(2, package_count)

    def test_missing_lock_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='missing-lock-', dir=SCRATCH) as name:
            root = Path(name)
            for relative in inputs.REQUIRED_INPUTS:
                if relative == inputs.LOCK_PATH:
                    continue
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{}\n')
            with self.assertRaisesRegex(
                    inputs.InstallInputError, 'missing required install input'):
                inputs.validate_source(root)

    def test_missing_settings_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='missing-settings-', dir=SCRATCH) as name:
            root = Path(name)
            for relative in inputs.REQUIRED_INPUTS:
                if relative == inputs.SETTINGS_PATH:
                    continue
                source = REPO / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            with self.assertRaisesRegex(
                    inputs.InstallInputError, 'missing required install input'):
                inputs.validate_source(root)

    def test_missing_boundary_module_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='missing-boundary-', dir=SCRATCH) as name:
            root = Path(name)
            self.copied_inputs(root)
            (root / inputs.BOUNDARY_PATH).unlink()
            with self.assertRaisesRegex(
                    inputs.InstallInputError, 'missing required install input'):
                inputs.validate_source(root)

    def test_ignored_lock_is_rejected(self):
        with self.assertRaisesRegex(
                inputs.InstallInputError, 'required install input is ignored'):
            inputs.git_input_state(
                REPO, Path('ignored-fixture/package-lock.json'))

    def edited(self, prefix, edit, message):
        with tempfile.TemporaryDirectory(prefix=prefix, dir=SCRATCH) as name:
            root = Path(name)
            self.copied_inputs(root)
            documents = {
                relative: json.loads((root / relative).read_text())
                for relative in (Path('native/npm/package.json'), inputs.LOCK_PATH,
                                 Path('native/toolchain.json'), inputs.AGENT_MANIFEST_PATH)
            }
            edit(*documents.values())
            for relative, document in documents.items():
                (root / relative).write_text(json.dumps(document))
            with self.assertRaisesRegex(inputs.InstallInputError, message):
                inputs.validate_source(root)

    def test_missing_agent_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='missing-agent-', dir=SCRATCH) as name:
            root = Path(name)
            self.copied_inputs(root)
            (root / inputs.AGENT_MANIFEST_PATH).unlink()
            with self.assertRaisesRegex(
                    inputs.InstallInputError, 'missing required install input'):
                inputs.validate_source(root)

    def test_lockfile_only_playwright_upgrade_fails_on_stale_apt_provenance(self):
        def edit(package, lock, manifest, agent):
            package['dependencies']['playwright'] = '1.64.0'
            lock['packages']['']['dependencies']['playwright'] = '1.64.0'
            entry = lock['packages']['node_modules/playwright']
            entry['version'] = '1.64.0'
            entry['resolved'] = entry['resolved'].replace('1.63.0', '1.64.0')
        self.edited('playwright-lock-only-', edit,
                    'Chromium apt source and locked Playwright version mismatch')

    def test_stale_apt_provenance_is_rejected(self):
        def edit(package, lock, manifest, agent):
            manifest['chromium_apt_source'] = manifest['chromium_apt_source'].replace(
                'playwright-core 1.63.0', 'playwright-core 1.62.0')
        self.edited('playwright-apt-', edit,
                    'Chromium apt source and locked Playwright version mismatch')

    def test_package_and_lock_disagreement_is_rejected(self):
        def edit(package, lock, manifest, agent):
            package['dependencies']['playwright'] = '1.64.0'
            lock['packages']['']['dependencies']['playwright'] = '1.64.0'
        self.edited('playwright-package-', edit,
                    'npm manifest and lock Playwright version mismatch')

    def test_root_dependency_disagreement_is_rejected(self):
        def edit(package, lock, manifest, agent):
            package['dependencies']['playwright'] = '1.64.0'
        self.edited('playwright-root-', edit,
                    'npm manifest and lock direct dependencies mismatch')

    def test_missing_transitive_integrity_is_rejected(self):
        def edit(package, lock, manifest, agent):
            del lock['packages']['node_modules/playwright-core']['integrity']
        self.edited('playwright-integrity-', edit,
                    'playwright-core: missing SHA-512 integrity')

    def test_non_registry_transitive_tarball_is_rejected(self):
        def edit(package, lock, manifest, agent):
            lock['packages']['node_modules/playwright-core']['resolved'] = (
                'http://registry.npmjs.org/playwright-core/-/playwright-core-1.63.0.tgz')
        self.edited('playwright-https-', edit, 'registry HTTPS tarball missing')

    def test_provider_cannot_return_to_the_locked_project(self):
        def edit(package, lock, manifest, agent):
            package['dependencies']['@openai/codex'] = '0.161.0'
            lock['packages']['']['dependencies']['@openai/codex'] = '0.161.0'
        self.edited('provider-lock-', edit,
                    'exactly the pinned Playwright project')

    def test_floating_provider_cannot_carry_a_pin(self):
        def edit(package, lock, manifest, agent):
            agent['providers']['codex']['version'] = '0.161.0'
        self.edited('provider-pin-', edit,
                    '@openai/codex: floating provider must not carry a pin')

if __name__ == '__main__':
    unittest.main()
