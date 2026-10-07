"""Assert repository-owned Renovate extraction identities against current files."""
import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
CONFIG = json.loads((REPO / 'renovate.json').read_text())
TOOLCHAIN_TEXT = (REPO / 'native/toolchain.json').read_text()
TOOLCHAIN = json.loads(TOOLCHAIN_TEXT)
WORKFLOW_TEXT = (
    REPO / '.github/workflows/native-dependency-validation.yml').read_text()

EXPECTED_CUSTOM_IDENTITIES = {
    ('kubernetes/kubernetes', 'github-releases'),
    ('helm/helm', 'github-releases'),
    ('tilt-dev/tilt', 'github-releases'),
    ('kubernetes-sigs/kind', 'github-releases'),
    ('rhysd/actionlint', 'github-releases'),
    ('go', 'golang-version'),
    ('mitmproxy', 'pypi'),
    ('node', 'node-version'),
}


class DependencyDiscoveryTests(unittest.TestCase):
    def test_custom_managers_extract_one_current_dependency_each(self):
        managers = CONFIG.get('customManagers', [])
        identities = {
            (manager.get('depNameTemplate'), manager.get('datasourceTemplate'))
            for manager in managers
        }
        self.assertEqual(EXPECTED_CUSTOM_IDENTITIES, identities)
        self.assertEqual(len(EXPECTED_CUSTOM_IDENTITIES), len(managers))

        extracted = {}
        for manager in managers:
            self.assertEqual(
                ['/^native\\/toolchain\\.json$/'],
                manager.get('managerFilePatterns'),
            )
            self.assertEqual(1, len(manager.get('matchStrings', [])))
            # The checked-in expressions use only syntax shared by RE2 and
            # Python apart from named-capture spelling.
            pattern = manager['matchStrings'][0].replace(
                '(?<currentValue>', '(?P<currentValue>')
            matches = list(re.finditer(pattern, TOOLCHAIN_TEXT))
            self.assertEqual(1, len(matches), manager['description'])
            extracted[manager['depNameTemplate']] = matches[0].group('currentValue')

        self.assertEqual(TOOLCHAIN['downloads']['kubectl']['version'],
                         extracted['kubernetes/kubernetes'])
        self.assertEqual(TOOLCHAIN['downloads']['helm']['version'],
                         extracted['helm/helm'])
        self.assertEqual(TOOLCHAIN['downloads']['tilt']['version'],
                         extracted['tilt-dev/tilt'])
        self.assertEqual(TOOLCHAIN['downloads']['kind']['version'],
                         extracted['kubernetes-sigs/kind'])
        self.assertEqual(TOOLCHAIN['downloads']['actionlint']['version'],
                         extracted['rhysd/actionlint'])
        self.assertEqual(TOOLCHAIN['downloads']['go']['version'], extracted['go'])
        self.assertEqual(TOOLCHAIN['user_tools']['mitmproxy']['version'],
                         extracted['mitmproxy'])
        self.assertEqual('24', extracted['node'])

    def test_standard_npm_discovery_owns_exact_direct_set(self):
        package = json.loads((REPO / 'native/npm/package.json').read_text())
        expected = {
            name: tool['version']
            for name, tool in TOOLCHAIN['user_tools'].items()
            if tool.get('method') == 'npm'
        }
        self.assertEqual(expected, package['dependencies'])

    def test_checksum_coupled_identities_are_approval_gated(self):
        rules = CONFIG.get('packageRules', [])
        checksum_rules = [
            rule for rule in rules
            if 'checksum-required' in rule.get('labels', [])
        ]
        self.assertEqual(1, len(checksum_rules))
        rule = checksum_rules[0]
        self.assertTrue(rule.get('dependencyDashboardApproval'))
        self.assertEqual(
            {
                'kubernetes/kubernetes', 'helm/helm', 'tilt-dev/tilt',
                'kubernetes-sigs/kind', 'rhysd/actionlint', 'go',
            },
            set(rule.get('matchPackageNames', [])),
        )

    def test_hosted_manual_inventory_covers_non_discovered_inputs(self):
        for required in (
                '$manifest[0].os', '$manifest[0].apt',
                '$manifest[0].chromium_apt', '$manifest[0].chromium_apt_source',
                '.value.source', '.value.fingerprint', '.value.policy',
                '$manifest[0].downloads.via',
                '$manifest[0].user_tools["ai-session-handler"]',
                '$manifest[0].user_tools.chromium'):
            self.assertIn(required, WORKFLOW_TEXT)


if __name__ == '__main__':
    unittest.main()
