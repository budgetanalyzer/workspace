"""Mocked checks for the personal-host development VM snapshot script."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO / 'scripts/snapshot-agent-vm.sh'


class VmSnapshotTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / 'tmp/vm-snapshot-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='snapshot-', dir=scratch)
        self.root = Path(self.temp.name)
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        self.dest = self.root / 'dest'
        self.dest.mkdir()
        self.log = self.root / 'virsh.log'
        self.state = self.root / 'state'
        self.state.write_text('running\n')
        self.disk = self.root / 'disk.qcow2'
        self.disk.write_text('disk-data\n')
        self.nvram = self.root / 'VM_VARS.fd'
        self.nvram.write_text('nvram\n')
        self.tpm = self.root / 'swtpm'
        (self.tpm / 'tpm2').mkdir(parents=True)
        (self.tpm / 'tpm2/tpm2-00.permall').write_text('tpm\n')
        self.xml = self.root / 'domain.xml'
        self._write_xml(f"<disk type='file' device='disk'><source file='{self.disk}'/>"
                        "<target dev='vda'/></disk>")
        self._fake('virsh', f'''
            echo "$*" >> {self.log}
            shift 2
            case "$1" in
              domstate) cat {self.state} ;;
              shutdown) echo 'shut off' > {self.state} ;;
              start) echo running > {self.state} ;;
              dumpxml) cat {self.xml} ;;
            esac
        ''')
        self._fake('qemu-img', '''
            case "$1" in
              convert) cp "${@: -2:1}" "${@: -1}" ;;
              check) ;;
            esac
        ''')
        self.env = dict(os.environ, PATH=f'{self.commands}:/usr/bin:/bin')

    def tearDown(self):
        self.temp.cleanup()

    def _fake(self, name, body):
        path = self.commands / name
        path.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + textwrap.dedent(body))
        path.chmod(0o755)

    def _write_xml(self, disks):
        self.xml.write_text(textwrap.dedent(f'''\
            <domain type='kvm'>
              <name>budget-analyzer-agent</name>
              <uuid>00000000-0000-0000-0000-000000000001</uuid>
              <os><nvram>{self.nvram}</nvram></os>
              <devices>
                {disks}
                <disk type='file' device='cdrom'><target dev='sda'/></disk>
                <tpm model='tpm-crb'><backend type='emulator' version='2.0'>
                  <source type='dir' path='{self.tpm}'/></backend></tpm>
              </devices>
            </domain>
        '''))

    def _run(self, *args):
        return subprocess.run([str(SNAPSHOT), *args], env=self.env, text=True,
                              capture_output=True)

    def test_cold_snapshot_copies_state_and_restarts(self):
        result = self._run(str(self.dest))
        self.assertEqual(result.returncode, 0, result.stderr)
        [snapshot] = list(self.dest.iterdir())
        self.assertTrue(snapshot.name.startswith('budget-analyzer-agent-'))
        self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
        self.assertEqual((snapshot / 'vda.qcow2').read_text(), 'disk-data\n')
        self.assertTrue((snapshot / 'VM_VARS.fd').is_file())
        self.assertTrue((snapshot / 'tpm/tpm2/tpm2-00.permall').is_file())
        self.assertFalse((snapshot / 'sda.qcow2').exists())
        subprocess.run(['sha256sum', '-c', '--quiet', 'SHA256SUMS'],
                       cwd=snapshot, check=True)
        calls = self.log.read_text()
        self.assertIn('shutdown budget-analyzer-agent', calls)
        self.assertNotIn('destroy', calls)
        self.assertTrue(calls.rstrip().endswith('start budget-analyzer-agent'))

    def test_shut_off_vm_is_not_started(self):
        self.state.write_text('shut off\n')
        result = self._run(str(self.dest))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('start', self.log.read_text().replace('domstate', ''))

    def test_non_local_disk_fails_and_restarts(self):
        self._write_xml("<disk type='network' device='disk'><source protocol='nbd'/>"
                        "<target dev='vda'/></disk>")
        result = self._run(str(self.dest))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('incomplete', result.stderr)
        self.assertEqual(self.state.read_text().strip(), 'running')

    def test_rejects_relative_root(self):
        result = self._run('relative/root')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
