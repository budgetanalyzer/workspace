#!/usr/bin/env python3
"""Human-run, read-only Mint host inspection; creates private evidence only."""

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


class AuditError(RuntimeError):
    pass


def run(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'LC_ALL': 'C', 'LIBVIRT_DEFAULT_URI': 'qemu:///system'})
        return result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 125, '', str(exc)


def require_host(confirmed):
    if not confirmed:
        raise AuditError('Pass --confirm-personal-host only from the human-operated Mint workstation.')
    if os.getuid() == 0:
        raise AuditError('Run as the normal host user after sudo -v, not as root.')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                   if '=' in line)
    if release.get('ID', '').strip('"') != 'linuxmint':
        raise AuditError('This collector targets the personal Linux Mint host; guest execution is refused.')
    if Path('/.dockerenv').exists() or Path('/run/.containerenv').exists():
        raise AuditError('Container execution is refused.')
    for mode in ('--container', '--vm'):
        code, output, _ = run(['systemd-detect-virt', mode])
        if code != 1 or output.strip() != 'none':
            raise AuditError('Expected the physical personal host; virtualization detection failed.')
    for tool in ('sudo', 'virsh', 'ufw', 'iptables-save', 'ip6tables-save', 'nft', 'ip', 'ss'):
        if not shutil.which(tool):
            raise AuditError(f'Missing host inspection prerequisite: {tool}; nothing will be installed.')
    if run(['sudo', '-n', 'true'])[0]:
        raise AuditError('Authorize reads with sudo -v in the human host shell first.')


class Redactor:
    """Best-effort candidate redaction. Human review is still mandatory."""
    def __init__(self, *, domain=None, network=None):
        self.identities = {}
        self.named_identifiers = {}
        if domain:
            self.remember_identifier('DOMAIN', domain)
        if network:
            self.remember_identifier('NETWORK', network)

    def alias(self, kind, value):
        key = (kind, value)
        if key not in self.identities:
            self.identities[key] = f'{kind}_{1 + sum(k[0] == kind for k in self.identities)}'
        return self.identities[key]

    def remember_identifier(self, kind, value):
        if value:
            self.named_identifiers[value] = self.alias(kind, value)

    def learn_xml(self, value):
        """Learn relationship-bearing names before rendering a shared report."""
        root = ET.fromstring(value)
        name = root.findtext('name')
        if root.tag == 'domain':
            self.remember_identifier('DOMAIN', name)
            for source in root.findall("./devices/interface/source[@network]"):
                self.remember_identifier('NETWORK', source.get('network'))
            for target in root.findall("./devices/interface/target[@dev]"):
                self.remember_identifier('TAP', target.get('dev'))
        elif root.tag == 'network':
            self.remember_identifier('NETWORK', name)
            for bridge in root.findall('./bridge[@name]'):
                self.remember_identifier('BRIDGE', bridge.get('name'))

    def named(self, value):
        for identifier in sorted(self.named_identifiers, key=len, reverse=True):
            value = re.sub(
                rf'(?<![A-Za-z0-9_]){re.escape(identifier)}(?![A-Za-z0-9_])',
                self.named_identifiers[identifier],
                value,
            )
        return value

    def address(self, match):
        value = match.group()
        literal, separator, prefix = value.partition('/')
        try:
            address = ipaddress.ip_address(literal)
        except ValueError:
            return value
        # Keep operational local/multicast ranges useful for rule review.
        private4 = address.version == 4 and any(address in ipaddress.ip_network(net)
                    for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
        private6 = address.version == 6 and address in ipaddress.ip_network('fc00::/7')
        if private4 or private6 or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
            return value
        suffix = separator + prefix if separator else ''
        return self.alias(f'IP{address.version}', address.compressed) + suffix

    def text(self, value):
        value = re.sub(r'(?m)^\s*#.*$', '', value)
        shell_word = (
            r'(?:(?:"(?:\\.|[^"\\])*")|(?:\'(?:\\.|[^\'\\])*\')|(?:\\.|[^\s])+)'
        )
        value = re.sub(r'(--comment(?:=|\s+))' + shell_word,
                       r'\1"REDACTED_COMMENT"', value)
        value = re.sub(r'(?<![\w-])(comment\s+)("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')',
                       r'\1"REDACTED_COMMENT"', value)
        value = self.named(value)
        value = re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b',
                       lambda m: self.alias('MAC', m.group().lower()), value)
        value = re.sub(
            r'(?i)((?:ether\s+(?:saddr|daddr)|link/ether|mac(?:\s+address)?[= :]+)\s*)'
            r'((?:[0-9a-f]{2}:){2,4}[0-9a-f]{2})(?![0-9a-f:])',
            lambda m: m.group(1) + self.alias('MAC_PREFIX', m.group(2).lower()),
            value,
        )
        value = re.sub(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
                       lambda m: self.alias('UUID', m.group().lower()), value)
        value = re.sub(r'(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?:/\d{1,3})?',
                       self.address, value)
        value = re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.])',
                       self.address, value)
        value = re.sub(r'/(?:home|root|data|mnt|media|srv)/[^\s\"\'<>]*',
                       lambda m: self.alias('PATH', m.group()), value)
        return value


DOCKER_PACKAGE_NAMES = frozenset({
    'containerd',
    'containerd.io',
    'docker-buildx',
    'docker-buildx-plugin',
    'docker-ce',
    'docker-ce-cli',
    'docker-ce-rootless-extras',
    'docker-cli',
    'docker-compose',
    'docker-compose-plugin',
    'docker-compose-v2',
    'docker.io',
    'moby-buildx',
    'moby-cli',
    'moby-compose',
    'moby-engine',
    'runc',
})


def docker_package_summary(value):
    """Return only installed Docker-engine/CLI and direct runtime families."""
    installed = []
    for line in value.splitlines():
        fields = line.split('\t')
        if len(fields) != 3:
            raise ValueError('Unexpected dpkg-query package record')
        package, status, version = fields
        package = package.rsplit(':', 1)[0]
        if package in DOCKER_PACKAGE_NAMES and len(status) > 1 and status[1] == 'i':
            installed.append(f'{package}\t{status}\t{version}')
    if not installed:
        return 'No installed Docker engine/CLI, containerd or runc package records.'
    return 'Installed Docker engine/CLI, containerd and runc package records:\n' + '\n'.join(sorted(installed))


def xml_summary(value):
    """Expose isolation-relevant structure without disk paths or identity XML."""
    root = ET.fromstring(value)
    if root.tag == 'domain':
        devices = root.find('devices')
        devices = devices if devices is not None else []
        result = {
            'domain_type': root.get('type'),
            'security_labels': [node.attrib for node in root.findall('seclabel')],
            'security_label_text_present': bool(root.findall('seclabel/label')),
            'custom_namespace_elements': sorted({node.tag for node in root.iter() if node.tag.startswith('{')}),
            'devices': [],
        }
        for node in devices:
            if node.tag in ('filesystem', 'hostdev', 'disk', 'interface', 'channel',
                            'graphics', 'redirdev', 'smartcard', 'tpm', 'vsock',
                            'shmem', 'serial', 'parallel', 'console'):
                entry = {'kind': node.tag, 'attributes': node.attrib, 'children': []}
                for child in node:
                    attrs = dict(child.attrib)
                    for key in ('file', 'dev', 'path', 'dir', 'socket'):
                        if key in attrs:
                            attrs[key] = 'HOST_PATH_PRESENT'
                    if child.tag == 'mac':
                        attrs = {'address': 'REDACTED_MAC'}
                    entry['children'].append({'kind': child.tag, 'attributes': attrs})
                result['devices'].append(entry)
        return json.dumps(result, indent=2)
    if root.tag == 'network':
        # Needed to connect guest interfaces, host bridge and firewall rules.
        for node in list(root):
            if node.tag in ('name', 'uuid', 'mac'):
                root.remove(node)
        for node in root.iter():
            for key in ('mac', 'name', 'hostname'):
                if key in node.attrib:
                    # Preserve the bridge name; redact DHCP client identities.
                    if not (node.tag == 'bridge' and key == 'name'):
                        node.set(key, 'REDACTED')
        return ET.tostring(root, encoding='unicode')
    raise ValueError('Unexpected libvirt XML root')


def collect(args, directory):
    redactor = Redactor(domain=args.domain, network=args.network)
    errors = []
    report = ['# Host isolation audit candidate',
              'Collection time UTC: ' + datetime.now(timezone.utc).isoformat(),
              'NOT A SECURITY PASS. Review privately before sharing. Local addresses,',
              'unselected interface names, chain/set names and process names are retained.',
              'Raw evidence and XML remain on the personal host. No active probes ran.']
    index = []

    def capture(label, argv, *, optional=False, xml=False, share=True, transform=None):
        code, output, error = run(argv)
        transform_failed = False
        if transform and not code:
            try:
                output = transform(output)
            except ValueError:
                transform_failed = True
                output = 'Output parsing failed; unfiltered output withheld.'
        elif transform and code:
            output = 'Command failed; unfiltered partial output withheld.'
        raw = directory / (label + '.txt')
        raw.write_text(f'exit={code}\nSTDOUT\n{output}\nSTDERR\n{error}')
        index.append({'name': raw.name, 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest(), 'exit': code})
        if code and not optional:
            errors.append(label)
        if transform_failed:
            errors.append(label + '-parse')
        report.extend(['', '## ' + label, f'exit={code}; optional={optional}'])
        if code:
            report.append('Unavailable or failed; inspect private raw output. Never count this as a denial.')
        elif share:
            if xml:
                try:
                    redactor.learn_xml(output)
                    output = xml_summary(output)
                except (ET.ParseError, ValueError):
                    errors.append(label + '-xml')
                    output = 'XML parsing failed; raw XML withheld.'
            report.extend(['```text', redactor.text(output).strip(), '```'])
        else:
            report.append('Private-only: inspect on host; share a manually redacted result if needed.')

    sudo = ['sudo', '-n', '--']
    virsh = sudo + ['virsh', '--connect', 'qemu:///system']
    # Learn live and persistent relationship names before rendering any rules.
    capture('domain-live', virsh + ['dumpxml', args.domain], xml=True)
    capture('domain-persistent', virsh + ['dumpxml', args.domain, '--inactive'], xml=True)
    capture('network-live', virsh + ['net-dumpxml', args.network], xml=True)
    capture('network-persistent', virsh + ['net-dumpxml', args.network, '--inactive'], xml=True)
    capture('ufw-status', sudo + ['ufw', 'status', 'verbose'])
    capture('ufw-numbered', sudo + ['ufw', 'status', 'numbered'])
    capture('ufw-effective', sudo + ['ufw', 'show', 'raw'])
    capture('iptables-v4', sudo + ['iptables-save', '-c'])
    capture('iptables-v6', sudo + ['ip6tables-save', '-c'])
    capture('nft-ruleset', sudo + ['nft', '-a', 'list', 'ruleset'])
    for name in ('iptables', 'ip6tables'):
        capture(name + '-backend', [name, '--version'])
    for name in ('iptables-legacy-save', 'ip6tables-legacy-save'):
        if shutil.which(name):
            capture(name, sudo + [name, '-c'])
    for name in ('before.rules', 'before6.rules', 'after.rules', 'after6.rules', 'user.rules', 'user6.rules'):
        capture('ufw-' + name, sudo + ['cat', '/etc/ufw/' + name])
    capture('ufw-defaults', sudo + ['cat', '/etc/default/ufw'])
    capture('ufw-enabled', sudo + ['cat', '/etc/ufw/ufw.conf'])
    capture('ufw-file-ownership', sudo + ['stat', '-c', '%U:%G %a %N', '/etc/ufw',
            '/etc/default/ufw', '/etc/ufw/ufw.conf', '/etc/ufw/before.rules',
            '/etc/ufw/before6.rules', '/etc/ufw/user.rules', '/etc/ufw/user6.rules',
            '/etc/ufw/after.rules', '/etc/ufw/after6.rules'])
    capture('ufw-service', ['systemctl', 'is-enabled', 'ufw.service'])
    capture('ufw-unit', ['systemctl', 'cat', 'ufw.service'], share=False)
    capture('ufw-hooks', sudo + ['cat', '/etc/ufw/after.init'], optional=True, share=False)
    capture('addresses', ['ip', '-details', 'address', 'show'])
    for family in ('-4', '-6'):
        capture('routes' + family, ['ip', family, 'route', 'show', 'table', 'all'])
        capture('policy' + family, ['ip', family, 'rule', 'show'])
    capture('listeners', sudo + ['ss', '-H', '-lntup'])
    capture('forwarding', ['sysctl', 'net.ipv4.ip_forward', 'net.ipv6.conf.all.forwarding'])
    capture('domain-state', virsh + ['domstate', args.domain])
    capture('domain-info', virsh + ['dominfo', args.domain])
    capture('network-info', virsh + ['net-info', args.network])
    capture('apparmor-status', sudo + ['aa-status'])
    # Label/process evidence helps distinguish configured from live confinement.
    capture('process-labels', ['ps', '-e', '-o', 'label=,comm='])
    capture('docker-units', ['systemctl', 'show', 'docker.service', 'docker.socket',
                            '-p', 'Id', '-p', 'LoadState', '-p', 'ActiveState', '-p', 'UnitFileState'])
    capture('docker-policy-files', sudo + ['stat', '-c', '%U:%G %a %N',
            '/usr/local/sbin/agent-vm-docker-isolation',
            '/etc/systemd/system/docker.service.d/agent-vm-isolation.conf'], optional=True)
    capture('docker-packages',
            ['dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Abbrev}\t${Version}\n'],
            transform=docker_package_summary)
    report.extend(['', '## Collection result',
                   'INCOMPLETE: ' + ', '.join(errors) if errors else 'COLLECTED: requires human and agent review; not a security verdict.',
                   'Review rule ordering, every input/forward path, protocol exceptions, live confinement,',
                   'persistent configuration and post-reboot paired probes using the audit runbook.'])
    (directory / 'candidate-report.md').write_text('\n'.join(report) + '\n')
    (directory / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-personal-host', action='store_true')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--network', required=True)
    parser.add_argument('--output-parent', type=Path, default=Path.home())
    args = parser.parse_args()
    try:
        require_host(args.confirm_personal_host)
        for value in (args.domain, args.network):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
                raise AuditError('Domain/network must be a simple libvirt name.')
        parent = args.output_parent
        if not parent.is_dir() or parent.resolve() != parent or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o022:
            raise AuditError('Output parent must be an existing canonical, user-owned directory without group/world write access.')
        repo = Path(__file__).resolve().parents[2]
        if parent == repo or repo in parent.parents:
            raise AuditError('Keep host evidence outside the repository; use the default host home directory.')
        os.umask(0o077)
        directory = Path(tempfile.mkdtemp(prefix='budget-host-audit-', dir=parent))
        result = collect(args, directory)
        print(f'Private evidence: {directory}')
        print('Review candidate-report.md before transferring only that redacted report. Keep raw files and index on the host.')
        print('Collection is INCOMPLETE.' if result else 'Collection finished; this is NOT an isolation pass.')
        return result
    except (AuditError, OSError) as exc:
        print(f'host-isolation-audit: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
