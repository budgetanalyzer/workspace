"""Focused native install-input closure and publication-policy checks."""
import importlib.util
from pathlib import Path
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
    def test_reviewed_source_is_complete(self):
        lock_hash, package_count = inputs.validate_source(REPO)
        self.assertEqual(
            'f42dff943f668e927407f16ef214f43ea2e88f319c9d0deae13e5b27f6df8b91',
            lock_hash,
        )
        self.assertGreater(package_count, 4)

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

    def test_ignored_lock_is_rejected(self):
        with self.assertRaisesRegex(
                inputs.InstallInputError, 'required install input is ignored'):
            inputs.git_input_state(
                REPO, Path('ignored-fixture/package-lock.json'))


if __name__ == '__main__':
    unittest.main()
