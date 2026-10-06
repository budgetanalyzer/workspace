"""Offline configuration and verifier-contract tests; never inspect the host."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / 'tests/host-isolation-audit/fixtures'
MODULE_PATH = REPO / 'scripts/host-isolation/host_isolation_config.py'
VERIFIER = REPO / 'scripts/host-isolation/verify-agent-host-isolation.sh'
spec = importlib.util.spec_from_file_location('host_isolation_config', MODULE_PATH)
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)


def fixture(name):
    return (FIXTURES / name).read_text()


def policy(config):
    rules = '\n'.join('    ' + rule for rule in config_module.expected_policy(config))
    return (
        'table inet budget_agent_host_input {\n'
        '  chain early_vm_host_input {\n'
        '    type filter hook input priority -190; policy accept;\n'
        f'{rules}\n'
        '  }\n'
        '}\n'
    )


def domain_xml(config, *, live=True):
    label = '<label>libvirt-fixture-label</label>' if live else ''
    target = '<target dev="fixturetap0"/>' if live else ''
    return (
        '<domain type="kvm">'
        f'<seclabel type="dynamic" model="apparmor">{label}</seclabel>'
        '<devices><interface type="network">'
        f'<mac address="{config["vm_mac"]}"/>'
        f'<source network="{config["vm_network"]}"/>{target}'
        '</interface><channel><target type="virtio" name="org.qemu.guest_agent.0"/>'
        '</channel><graphics type="vnc" listen="127.0.0.1">'
        '<listen type="address" address="127.0.0.1"/></graphics></devices></domain>'
    )


def network_xml(config):
    prefix = config_module.guest_prefix(config)
    address = config_module.guest_address(config)
    return (
        f'<network><name>{config["vm_network"]}</name>'
        f'<bridge name="{config["vm_bridge"]}"/><forward mode="nat"/>'
        f'<ip address="{config["vm_gateway"]}" prefix="{prefix}"><dhcp>'
        f'<host mac="{config["vm_mac"]}" ip="{address}"/>'
        '</dhcp></ip></network>'
    )


class ConfigTests(unittest.TestCase):
    def test_valid_fixture_substitutes_every_policy_topology_value(self):
        config = config_module.parse_text(fixture('config-valid.conf'))
        rendered = '\n'.join(config_module.expected_policy(config))
        for expected in ('fixturebr0', '02:00:5e:00:53:01', '192.0.2.10',
                         '192.0.2.1', '192.0.2.255'):
            self.assertIn(expected, rendered)
        self.assertNotIn('<', rendered)
        config_module.validate_policy(config, policy(config), policy(config))
        config_module.validate_domain_xml(domain_xml(config), config, True)
        config_module.validate_domain_xml(domain_xml(config, live=False), config, False)
        config_module.validate_network_xml(network_xml(config), config)

    def test_missing_malformed_unknown_and_duplicate_values_are_rejected(self):
        for name in ('config-missing.conf', 'config-malformed.conf',
                     'config-unknown.conf', 'config-duplicate.conf'):
            with self.subTest(name=name), self.assertRaises(config_module.ConfigError):
                config_module.parse_text(fixture(name))

    def test_placeholder_template_is_not_accepted_as_live_configuration(self):
        template = (REPO / 'scripts/host-isolation/host-isolation-config.example').read_text()
        with self.assertRaises(config_module.ConfigError):
            config_module.parse_text(template)

    def test_unsafe_mode_symlink_and_unexpected_owner_are_rejected(self):
        scratch = REPO / 'tmp/host-audit-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            root = Path(name)
            private = root / 'private.conf'
            private.write_text(fixture('config-valid.conf'))
            private.chmod(0o600)
            self.assertEqual('fixture-domain',
                             config_module.load(private, expected_uid=os.getuid())['vm_domain'])

            private.chmod(0o620)
            with self.assertRaises(config_module.ConfigError):
                config_module.load(private, expected_uid=os.getuid())
            private.chmod(0o644)
            with self.assertRaises(config_module.ConfigError):
                config_module.load(private, expected_uid=os.getuid())
            private.chmod(0o600)

            link = root / 'linked.conf'
            link.symlink_to(private)
            with self.assertRaises(config_module.ConfigError):
                config_module.load(link, expected_uid=os.getuid())
            with self.assertRaises(config_module.ConfigError):
                config_module.load(private, expected_uid=os.getuid() + 1)

    def test_syntactically_valid_drift_fails_network_and_policy_comparison(self):
        reviewed = config_module.parse_text(fixture('config-valid.conf'))
        drifted = config_module.parse_text(fixture('config-drifted.conf'))
        with self.assertRaises(config_module.ConfigError):
            config_module.validate_network_xml(network_xml(reviewed), drifted)
        with self.assertRaises(config_module.ConfigError):
            config_module.validate_policy(drifted, policy(reviewed), policy(reviewed))


class VerifierContractTests(unittest.TestCase):
    def test_missing_explicit_config_is_binary_error_without_host_reads(self):
        result = subprocess.run([str(VERIFIER)], capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertEqual('ERROR\n', result.stdout)
        self.assertEqual('', result.stderr)

    def test_verifier_has_no_embedded_private_topology(self):
        text = VERIFIER.read_text()
        forbidden_values = (
            ':'.join(('52', '54', '00', 'd9', 'c2', '70')),
            '.'.join(('192', '168', '231', '')),
            ''.join(('vir', 'br1')),
        )
        for forbidden in forbidden_values:
            self.assertNotIn(forbidden, text)
        self.assertIn('load_config "$@"', text)
        self.assertIn('LIBVIRT_UNITS', text)


if __name__ == '__main__':
    unittest.main()
