#!/usr/bin/env python3
"""Strict private configuration and pure validators for host isolation."""

import argparse
import ipaddress
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import xml.etree.ElementTree as ET


KEYS = (
    'vm_domain',
    'vm_network',
    'vm_bridge',
    'vm_mac',
    'vm_ipv4',
    'vm_gateway',
    'dhcp_broadcast',
    'policy_service',
    'policy_file',
    'policy_loader',
    'policy_unit',
    'required_units',
)
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
INTERFACE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,14}')
UNIT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.@:-]{0,254}\.(?:service|socket)')
PATH_VALUE = re.compile(r'/[A-Za-z0-9_./-]+')
MAC = re.compile(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}')


class ConfigError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ConfigError(message)


def parse_text(text):
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        require(raw == line and line.count('=') == 1,
                f'line {number}: expected an unquoted key=value assignment')
        key, value = line.split('=', 1)
        require(key in KEYS, f'line {number}: unknown key: {key}')
        require(key not in values, f'line {number}: duplicate key: {key}')
        require(value and value == value.strip(), f'line {number}: empty or padded value')
        require(not any(token in value for token in ('<', '>', 'REPLACE_', 'CHANGE_ME')),
                f'line {number}: placeholder value is not a live configuration')
        require(not any(ord(character) < 32 or ord(character) == 127 for character in value),
                f'line {number}: control character in value')
        values[key] = value
    missing = [key for key in KEYS if key not in values]
    require(not missing, 'missing keys: ' + ', '.join(missing))
    return validate(values)


def validate(values):
    result = dict(values)
    for key in ('vm_domain', 'vm_network'):
        require(bool(NAME.fullmatch(result[key])) and result[key] not in ('.', '..'),
                f'invalid {key}')
    require(bool(INTERFACE.fullmatch(result['vm_bridge'])), 'invalid vm_bridge')
    require(bool(MAC.fullmatch(result['vm_mac'])), 'invalid vm_mac')
    octets = bytes.fromhex(result['vm_mac'].replace(':', ''))
    require(not octets[0] & 1 and any(octets), 'vm_mac must be a nonzero unicast address')
    result['vm_mac'] = result['vm_mac'].lower()

    try:
        guest = ipaddress.ip_interface(result['vm_ipv4'])
        gateway = ipaddress.ip_address(result['vm_gateway'])
        broadcast = ipaddress.ip_address(result['dhcp_broadcast'])
    except ValueError as exc:
        raise ConfigError(f'invalid IPv4 topology: {exc}') from exc
    require(guest.version == gateway.version == broadcast.version == 4,
            'vm_ipv4, vm_gateway and dhcp_broadcast must be IPv4')
    require(1 <= guest.network.prefixlen <= 30, 'vm_ipv4 prefix must be between 1 and 30')
    require(gateway in guest.network and gateway != guest.ip,
            'vm_gateway must be another address in the guest subnet')
    require(broadcast in (ipaddress.ip_address('255.255.255.255'), guest.network.broadcast_address),
            'dhcp_broadcast must be the subnet or limited broadcast address')
    result['vm_ipv4'] = str(guest)
    result['vm_gateway'] = str(gateway)
    result['dhcp_broadcast'] = str(broadcast)

    require(bool(UNIT.fullmatch(result['policy_service']))
            and result['policy_service'].endswith('.service'), 'invalid policy_service')
    for key in ('policy_file', 'policy_loader', 'policy_unit'):
        value = result[key]
        require(bool(PATH_VALUE.fullmatch(value)), f'invalid {key}')
        parsed = PurePosixPath(value)
        require(parsed.is_absolute() and '..' not in parsed.parts and str(parsed) == value,
                f'{key} must be a normalized absolute path')
    require(PurePosixPath(result['policy_unit']).name == result['policy_service'],
            'policy_unit basename must match policy_service')

    units = result['required_units'].split(',')
    require(all(units) and all(UNIT.fullmatch(unit) for unit in units),
            'required_units must be a comma-separated service/socket list')
    require(len(units) == len(set(units)), 'required_units contains a duplicate')
    require(result['policy_service'] not in units, 'required_units must not contain policy_service')
    result['required_units'] = ','.join(units)
    return result


def load(path, expected_uid=0):
    path = Path(path)
    require(path.is_absolute(), 'configuration path must be absolute')
    require(path.exists(), 'configuration is missing')
    require(not path.is_symlink(), 'configuration must not be a symlink')
    require(path.is_file(), 'configuration must be a regular file')
    require(path.resolve() == path, 'configuration path must be canonical')
    metadata = path.stat()
    require(metadata.st_uid == expected_uid, 'configuration has unexpected ownership')
    mode = stat.S_IMODE(metadata.st_mode)
    require(mode in (0o600, 0o640), 'configuration mode must be 0600 or 0640')
    return parse_text(path.read_text())


def guest_address(config):
    return str(ipaddress.ip_interface(config['vm_ipv4']).ip)


def guest_prefix(config):
    return ipaddress.ip_interface(config['vm_ipv4']).network.prefixlen


def expected_policy(config):
    bridge = config['vm_bridge']
    mac = config['vm_mac']
    address = guest_address(config)
    gateway = config['vm_gateway']
    broadcast = config['dhcp_broadcast']
    return [
        f'iifname "{bridge}" ether saddr != {mac} counter drop',
        f'iifname "{bridge}" ct state established,related counter accept',
        (f'iifname "{bridge}" ether saddr {mac} ip saddr {address} '
         f'ip daddr {gateway} meta l4proto {{ tcp, udp }} th dport 53 counter accept'),
        (f'iifname "{bridge}" ether saddr {mac} ip saddr {{ 0.0.0.0, {address} }} '
         f'ip daddr {{ {gateway}, {broadcast} }} udp sport 68 udp dport 67 counter accept'),
        f'iifname "{bridge}" udp dport {{ 1900, 5353 }} counter drop',
        f'iifname "{bridge}" counter drop',
    ]


def normalize_rule(value):
    value = re.sub(r'\\\n[ \t]*', ' ', value)
    value = re.sub(r'[ \t]+', ' ', value.strip())
    value = re.sub(r'counter packets \d+ bytes \d+', 'counter', value)
    return re.sub(r'\s+# handle \d+\s*$', '', value)


def extract_policy(text, live):
    text = re.sub(r'\\\n[ \t]*', ' ', text)
    lines = [normalize_rule(line) for line in text.splitlines()]
    require([line for line in lines if line.startswith('table ')]
            == ['table inet budget_agent_host_input {'], 'unexpected policy table')
    require([line for line in lines if line.startswith('chain ')]
            == ['chain early_vm_host_input {'], 'unexpected policy chain')
    hooks = [line for line in lines if line.startswith('type filter hook input')]
    require(len(hooks) == 1 and 'policy accept;' in hooks[0]
            and re.search(r'priority (?:filter )?-\s*190;', hooks[0]),
            'unexpected policy hook')
    rules = []
    for line in lines:
        if line in ('', '{', '}') or line.startswith(('table ', 'chain ', 'type filter hook input')):
            continue
        if not live and line.startswith('#'):
            continue
        rules.append(line)
    return rules


def validate_policy(config, live_text, source_text):
    expected = expected_policy(config)
    require(extract_policy(live_text, True) == expected, 'live policy differs from configuration')
    require(extract_policy(source_text, False) == expected, 'policy source differs from configuration')


def one(nodes):
    require(len(nodes) == 1, 'expected exactly one XML element')
    return nodes[0]


def validate_domain_xml(text, config, live):
    root = ET.fromstring(text)
    require(root.tag == 'domain' and root.get('type') == 'kvm', 'unexpected domain type')
    labels = [node for node in root.findall('seclabel')
              if node.get('type') == 'dynamic' and node.get('model') == 'apparmor']
    label = one(labels).findtext('label') if live else None
    require(not live or bool(label), 'missing live AppArmor label')
    devices = one(root.findall('devices'))
    forbidden = {'filesystem', 'hostdev', 'redirdev', 'smartcard', 'shmem', 'vsock'}
    require(not any(device.tag in forbidden for device in devices), 'forbidden host integration')
    namespace = 'http://libvirt.org/schemas/domain/qemu/1.0'
    require(not any(node.tag.startswith('{' + namespace + '}') for node in root.iter()),
            'custom QEMU integration is forbidden')
    interface = one(devices.findall('interface'))
    source = one(interface.findall('source'))
    mac = one(interface.findall('mac')).get('address', '').lower()
    require(interface.get('type') == 'network'
            and source.get('network') == config['vm_network']
            and mac == config['vm_mac'], 'domain network identity drift')
    for channel in devices.findall('channel'):
        target = one(channel.findall('target'))
        require(target.get('type') == 'virtio'
                and target.get('name') == 'org.qemu.guest_agent.0',
                'unexpected domain channel')
    for graphics in devices.findall('graphics'):
        require(graphics.get('type') == 'vnc' and graphics.get('listen') == '127.0.0.1',
                'graphics must be loopback-only VNC')
        for listen in graphics.findall('listen'):
            require(listen.get('type') == 'address' and listen.get('address') == '127.0.0.1',
                    'graphics listener drift')
    target = interface.find('target')
    tap = target.get('dev') if live and target is not None else None
    require(not live or bool(tap), 'missing live tap')
    return mac, tap, label


def validate_network_xml(text, config):
    root = ET.fromstring(text)
    require(root.tag == 'network' and root.findtext('name') == config['vm_network'],
            'network identity drift')
    bridge = one(root.findall('bridge'))
    forward = one(root.findall('forward'))
    require(bridge.get('name') == config['vm_bridge'] and forward.get('mode') == 'nat',
            'bridge or forwarding drift')
    ipv4 = [node for node in root.findall('ip') if ':' not in node.get('address', '')]
    ip_node = one(ipv4)
    require(ip_node.get('address') == config['vm_gateway'], 'gateway drift')
    prefix = str(guest_prefix(config))
    netmask = str(ipaddress.ip_interface(config['vm_ipv4']).network.netmask)
    require(ip_node.get('prefix') == prefix or ip_node.get('netmask') == netmask,
            'network prefix drift')
    address = guest_address(config)
    require(any(node.get('mac', '').lower() == config['vm_mac'] and node.get('ip') == address
                for node in ip_node.findall('./dhcp/host')), 'DHCP reservation drift')


def command(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('emit', 'check-policy'))
    parser.add_argument('config', type=Path)
    args = parser.parse_args(argv)
    try:
        config = load(args.config)
        if args.action == 'emit':
            for key in KEYS:
                print(config[key])
        else:
            validate_policy(config, os.environ['BA_LIVE_RULES'],
                            Path(config['policy_file']).read_text())
        return 0
    except (ConfigError, KeyError, OSError, ET.ParseError) as exc:
        print(f'host-isolation-config: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(command())
