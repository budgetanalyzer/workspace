"""Offline audit safety checks; never inspect or mutate the real host."""
import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'collector', REPO / 'scripts/host-isolation/collect-host-isolation-evidence.py'
)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def test_no_confirmation_never_runs_commands(self):
        with patch.object(collector, 'run') as command:
            with self.assertRaises(collector.AuditError):
                collector.require_host(False)
            command.assert_not_called()

    def test_guest_rejected_before_privileged_reads(self):
        with patch.object(collector.os, 'getuid', return_value=1000), \
                patch.object(Path, 'read_text', return_value='ID=ubuntu\n'), \
                patch.object(collector, 'run') as command:
            with self.assertRaises(collector.AuditError):
                collector.require_host(True)
            command.assert_not_called()

    def test_redaction_preserves_order_and_local_rule_semantics(self):
        redactor = collector.Redactor(domain='private-domain', network='private-network')
        redactor.learn_xml(
            '<domain><name>private-domain</name><devices><interface>'
            '<source network="private-network"/><target dev="private-tap42"/>'
            '</interface></devices></domain>'
        )
        redactor.learn_xml(
            '<network><name>private-network</name><bridge name="private-bridge42"/></network>'
        )
        rules = ('-A before -d 224.0.0.251 -p udp --dport 5353 -j ACCEPT\n'
                 '-A input -i private-bridge42 -s 10.123.45.0/24 -j DROP\n'
                 '-A input -i private-tap42 -s 203.0.113.0/24 '
                 '-m comment --comment "private identity with spaces" -j DROP\n'
                 'add rule inet private-network input comment "another private value" drop\n'
                 'private-domain private-network private-bridge42 private-tap42\n'
                 '2001:4860:4860::8888/64 aa:bb:cc:dd:ee:ff /home/person/secrets\n')
        result = redactor.text(rules)
        for hidden in ('203.0.113.0', 'private identity', 'another private value',
                       '2001:4860:4860::8888', 'aa:bb:cc:dd:ee:ff', '/home/person',
                       'private-domain', 'private-network', 'private-bridge42', 'private-tap42'):
            self.assertNotIn(hidden, result)
        self.assertIn('IP4_1/24', result)
        self.assertIn('IP6_1/64', result)
        self.assertIn('10.123.45.0/24', result)
        self.assertEqual(2, result.count('NETWORK_1'))
        self.assertEqual(2, result.count('BRIDGE_1'))
        self.assertEqual(2, result.count('TAP_1'))
        self.assertLess(result.index('5353'), result.index('BRIDGE_1'))
        self.assertIn('-m comment --comment "REDACTED_COMMENT"', result)
        self.assertIn('-j ACCEPT', result)
        self.assertIn('-j DROP', result)

    def test_short_mac_context_is_redacted_without_changing_ipv6(self):
        redactor = collector.Redactor()
        result = redactor.text('ether saddr 52:54:00 and route fe80::1/64\n')
        self.assertNotIn('52:54:00', result)
        self.assertIn('MAC_PREFIX_1', result)
        self.assertIn('fe80::1/64', result)

    def test_docker_package_summary_distinguishes_empty_and_filters_unrelated(self):
        records = ('docker.io:amd64\tii \t26.1\n'
                   'containerd\tii \t1.7\n'
                   'docker-ce-cli\thi \t26.1\n'
                   'unrelated-package\tii \t9.9\n'
                   'docker-ce\trc \t25.0\n')
        result = collector.docker_package_summary(records)
        self.assertIn('docker.io', result)
        self.assertIn('containerd', result)
        self.assertIn('docker-ce-cli', result)
        self.assertNotIn('unrelated-package', result)
        self.assertFalse(any(line.startswith('docker-ce\t') for line in result.splitlines()))
        self.assertIn('No installed', collector.docker_package_summary('unrelated-package\tii \t9.9\n'))

    def test_xml_keeps_host_integration_visible_without_paths(self):
        xml = ('<domain type="kvm"><seclabel type="dynamic" model="apparmor"/>'
               '<devices><filesystem type="mount"><source dir="/home/person"/>'
               '</filesystem><channel type="unix"><source path="/private/socket"/>'
               '</channel></devices></domain>')
        result = collector.xml_summary(xml)
        self.assertIn('filesystem', result)
        self.assertIn('channel', result)
        self.assertIn('apparmor', result)
        self.assertNotIn('/home/person', result)
        self.assertNotIn('/private/socket', result)

    def test_synthetic_collection_aliases_relationships_and_filters_packages(self):
        scratch = REPO / 'tmp/host-audit-tests'
        scratch.mkdir(parents=True, exist_ok=True)

        def fake_run(argv):
            if 'dumpxml' in argv:
                return 0, ('<domain><name>synthetic-domain</name><devices><interface>'
                           '<source network="synthetic-network"/>'
                           '<target dev="synthetic-tap"/></interface></devices></domain>'), ''
            if 'net-dumpxml' in argv:
                return 0, ('<network><name>synthetic-network</name>'
                           '<bridge name="synthetic-bridge"/></network>'), ''
            if argv and argv[0] == 'dpkg-query':
                return 0, ('docker.io\tii \t26.1\n'
                           'unrelated-package\tii \t9.9\n'), ''
            return 0, ('synthetic-domain synthetic-network synthetic-bridge synthetic-tap '
                       '203.0.113.0/24 -m comment --comment "private fixture identity"'), ''

        with tempfile.TemporaryDirectory(dir=scratch) as name, \
                patch.object(collector, 'run', side_effect=fake_run), \
                patch.object(collector.shutil, 'which', return_value=None):
            directory = Path(name)
            code = collector.collect(
                argparse.Namespace(domain='synthetic-domain', network='synthetic-network'),
                directory,
            )
            self.assertEqual(0, code)
            report = (directory / 'candidate-report.md').read_text()
            for hidden in ('synthetic-domain', 'synthetic-network', 'synthetic-bridge',
                           'synthetic-tap', '203.0.113.0', 'private fixture identity',
                           'unrelated-package'):
                self.assertNotIn(hidden, report)
            for expected in ('DOMAIN_1', 'NETWORK_1', 'BRIDGE_1', 'TAP_1',
                             'IP4_1/24', 'docker.io'):
                self.assertIn(expected, report)
            package_raw = (directory / 'docker-packages.txt').read_text()
            self.assertIn('docker.io', package_raw)
            self.assertNotIn('unrelated-package', package_raw)

    def test_failed_required_capture_cannot_produce_completed_collection(self):
        scratch = REPO / 'tmp/host-audit-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        calls = []

        def fake_run(argv):
            calls.append(argv)
            if 'iptables-save' in argv:
                return 1, '', 'private error detail'
            if 'dumpxml' in argv:
                return 0, '<domain type="kvm"><devices/></domain>', ''
            if 'net-dumpxml' in argv:
                return 0, '<network><bridge name="fixturebr0"/></network>', ''
            if argv and argv[0] == 'dpkg-query':
                return 1, 'docker.io\tii \tprivate-version\n', 'query failed'
            return 0, 'fixture output', ''

        with tempfile.TemporaryDirectory(dir=scratch) as name, \
                patch.object(collector, 'run', side_effect=fake_run), \
                patch.object(collector.shutil, 'which', return_value=None):
            directory = Path(name)
            code = collector.collect(argparse.Namespace(domain='fixture', network='fixture'), directory)
            self.assertEqual(1, code)
            report = (directory / 'candidate-report.md').read_text()
            self.assertIn('INCOMPLETE: iptables-v4', report)
            self.assertIn('docker-packages', report)
            self.assertNotIn('private-version', report)
            self.assertNotIn('private error detail', report)
            self.assertIn('private error detail', (directory / 'iptables-v4.txt').read_text())
            self.assertNotIn('private-version', (directory / 'docker-packages.txt').read_text())
            self.assertIn('unfiltered partial output withheld',
                          (directory / 'docker-packages.txt').read_text())
            self.assertIn('NOT A SECURITY PASS', report)
        for argv in calls:
            self.assertNotIn('ssh', argv)
            self.assertNotIn('docker', argv)
            for forbidden in ('reload', 'restart', 'enable', 'disable', 'apply', 'flush', '-F', '-A', '-I'):
                self.assertNotIn(forbidden, argv)


if __name__ == '__main__':
    unittest.main()
