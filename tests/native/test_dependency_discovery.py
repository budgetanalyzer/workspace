"""Assert repository-owned Renovate extraction identities against current files."""
import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
CONFIG = json.loads((REPO / 'renovate.json').read_text())
TOOLCHAIN_TEXT = (REPO / 'native/toolchain.json').read_text()
TOOLCHAIN = json.loads(TOOLCHAIN_TEXT)
AGENT_TEXT = (REPO / 'native/agent-tools.json').read_text()
AGENT = json.loads(AGENT_TEXT)
MANIFEST_TEXT = {
    '/^native\\/toolchain\\.json$/': TOOLCHAIN_TEXT,
    '/^native\\/agent-tools\\.json$/': AGENT_TEXT,
}
EXPECTED_MANIFEST = {
    'rhysd/actionlint': '/^native\\/toolchain\\.json$/',
    'go': '/^native\\/toolchain\\.json$/',
    'node': '/^native\\/toolchain\\.json$/',
    'mitmproxy': '/^native\\/agent-tools\\.json$/',
}
PROVIDERS = ('@anthropic-ai/claude-code', '@openai/codex', '@google/gemini-cli')
WORKFLOW_TEXT = (
    REPO / '.github/workflows/native-dependency-validation.yml').read_text()

EXPECTED_CUSTOM_IDENTITIES = {
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
            file_pattern = EXPECTED_MANIFEST[manager['depNameTemplate']]
            self.assertEqual([file_pattern], manager.get('managerFilePatterns'))
            self.assertEqual(1, len(manager.get('matchStrings', [])))
            # The checked-in expressions use only syntax shared by RE2 and
            # Python apart from named-capture spelling.
            pattern = manager['matchStrings'][0].replace(
                '(?<currentValue>', '(?P<currentValue>')
            matches = list(re.finditer(pattern, MANIFEST_TEXT[file_pattern]))
            self.assertEqual(1, len(matches), manager['description'])
            extracted[manager['depNameTemplate']] = matches[0].group('currentValue')

        self.assertEqual(TOOLCHAIN['downloads']['actionlint']['version'],
                         extracted['rhysd/actionlint'])
        self.assertEqual(TOOLCHAIN['downloads']['go']['version'], extracted['go'])
        self.assertEqual(AGENT['user_tools']['mitmproxy']['version'],
                         extracted['mitmproxy'])
        self.assertEqual('24', extracted['node'])

    def test_standard_npm_discovery_tracks_only_locked_playwright(self):
        package = json.loads((REPO / 'native/npm/package.json').read_text())
        lock = json.loads((REPO / 'native/npm/package-lock.json').read_text())
        self.assertEqual(
            {'playwright': lock['packages']['node_modules/playwright']['version']},
            package['dependencies'])

    def test_floating_providers_have_no_discovery_identity(self):
        renovate_text = (REPO / 'renovate.json').read_text()
        npm_text = ''.join(
            (REPO / 'native/npm' / name).read_text()
            for name in ('package.json', 'package-lock.json'))
        self.assertEqual(set(PROVIDERS),
                         {p['package'] for p in AGENT['providers'].values()})
        for package in PROVIDERS:
            self.assertNotIn(package, renovate_text)
            self.assertNotIn(package, npm_text)
            self.assertNotIn(package, TOOLCHAIN_TEXT)
        for provider in AGENT['providers'].values():
            self.assertFalse({'version', 'integrity', 'tarball'} & set(provider))

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
            {'rhysd/actionlint', 'go'},
            set(rule.get('matchPackageNames', [])),
        )

    def test_hosted_manual_inventory_covers_non_discovered_inputs(self):
        for required in (
                '$manifest[0].os', '$manifest[0].apt',
                '$manifest[0].chromium_apt', '$manifest[0].chromium_apt_source',
                '.value.source', '.value.fingerprint', '.value.policy',
                '$manifest[0].downloads.via',
                '$agent[0].user_tools["ai-session-handler"]',
                '$agent[0].user_tools.chromium'):
            self.assertIn(required, WORKFLOW_TEXT)


if __name__ == '__main__':
    unittest.main()
