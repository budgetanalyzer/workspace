#!/usr/bin/env python3
"""Bounded UDP fixture for human-run host-isolation protocol evidence."""

import argparse
import errno
import ipaddress
import os
import re
import secrets
import socket
import struct
import sys
import time


MAGIC = b'budget-host-isolation-v1:'
NONCE_PATTERN = re.compile(r'[A-Za-z0-9._-]{16,128}')


class FixtureError(RuntimeError):
    pass


def family_value(name):
    return socket.AF_INET if name == 'ipv4' else socket.AF_INET6


def high_port(value):
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('port must be an integer') from exc
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError('port must be between 1024 and 65535')
    return port


def interface_index(name):
    try:
        return socket.if_nametoindex(name)
    except OSError as exc:
        raise FixtureError(f'Selected interface is unavailable: {name}') from exc


def parse_address(value, family, *, allow_multicast=True):
    literal = value.split('%', 1)[0]
    try:
        address = ipaddress.ip_address(literal)
    except ValueError as exc:
        raise FixtureError(f'Invalid {family} address: {value}') from exc
    expected = 4 if family == 'ipv4' else 6
    if address.version != expected:
        raise FixtureError(f'Address family mismatch for {value}')
    if address.is_unspecified:
        raise FixtureError('Wildcard addresses are forbidden; select one interface address.')
    if address.is_multicast and not allow_multicast:
        raise FixtureError('Select a unicast interface address, not a multicast group.')
    return address


def validate_nonce(value):
    if not NONCE_PATTERN.fullmatch(value):
        raise FixtureError('Nonce must contain 16-128 ASCII letters, digits, dots, underscores or hyphens.')
    return value


def payload(nonce):
    return MAGIC + validate_nonce(nonce).encode('ascii')


def source_literal(sockaddr):
    return str(ipaddress.ip_address(sockaddr[0].split('%', 1)[0]))


def endpoint(address, port, family, interface=None):
    if family == 'ipv4':
        return (address, port)
    scope_id = 0
    if '%' in address:
        _, scope = address.rsplit('%', 1)
        scope_id = int(scope) if scope.isdigit() else interface_index(scope)
    elif interface:
        scope_id = interface_index(interface)
    return (address.split('%', 1)[0], port, 0, scope_id)


def emit_stdout(message):
    print(message, flush=True)


def open_listener(args):
    family = family_value(args.family)
    bind_address = parse_address(args.bind_address, args.family, allow_multicast=False)
    group = None
    if args.multicast_group:
        group = parse_address(args.multicast_group, args.family)
        if not group.is_multicast:
            raise FixtureError('--multicast-group must be multicast.')
        if not args.interface:
            raise FixtureError('--interface is required for multicast membership.')
        selected_interface_index = interface_index(args.interface)
    sock = socket.socket(family, socket.SOCK_DGRAM)
    try:
        if group:
            sock.bind(endpoint(str(group), args.port, args.family, args.interface))
            if family == socket.AF_INET:
                membership = socket.inet_aton(str(group)) + socket.inet_aton(str(bind_address))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            else:
                membership = socket.inet_pton(socket.AF_INET6, str(group))
                membership += struct.pack('@I', selected_interface_index)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, membership)
        else:
            sock.bind(endpoint(args.bind_address, args.port, args.family))
        sock.settimeout(min(0.25, args.timeout))
        return sock
    except (OSError, ValueError) as exc:
        sock.close()
        if isinstance(exc, OSError) and exc.errno == errno.EADDRINUSE:
            raise FixtureError('Selected address/port is occupied; do not reuse or stop its owner.') from exc
        raise FixtureError(f'Listener setup failed: {exc}') from exc


def run_listener(args, emit=emit_stdout):
    control = payload(args.control_nonce)
    probe = payload(args.probe_nonce)
    if control == probe:
        raise FixtureError('Control and guest-probe nonces must differ.')
    expected_control_source = str(parse_address(args.control_source_address, args.family,
                                                allow_multicast=False))
    expected_probe_source = str(parse_address(args.probe_source_address, args.family,
                                              allow_multicast=False))
    control_seen = False
    probe_seen = False
    deadline = time.monotonic() + args.timeout
    with open_listener(args) as sock:
        emit('LISTENER_READY selected-address-and-port-only')
        while time.monotonic() < deadline:
            try:
                data, sender = sock.recvfrom(2048)
            except socket.timeout:
                continue
            sender_address = source_literal(sender)
            if data == control and sender_address == expected_control_source:
                control_seen = True
                emit('CONTROL_RECEIVED expected-source')
            elif data == probe and sender_address == expected_probe_source:
                probe_seen = True
                emit('PROBE_DELIVERED expected-guest-source')
            elif data.startswith(MAGIC):
                emit('IGNORED_FIXTURE_PAYLOAD unexpected-source-or-nonce')
    if probe_seen:
        emit('FAIL probe reached receiver')
        return 1
    if not control_seen:
        emit('NOT_TESTED positive control was not received')
        return 3
    emit('RECEIVER_NON_DELIVERY_WITH_CONTROL requires separate ingress/drop attribution')
    return 0


def run_sender(args, emit=emit_stdout):
    family = family_value(args.family)
    source = parse_address(args.source_address, args.family, allow_multicast=False)
    destination = parse_address(args.destination_address, args.family)
    if destination.is_multicast and not args.interface:
        raise FixtureError('--interface is required for multicast sending.')
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.bind(endpoint(args.source_address, 0, args.family, args.interface))
        if destination.is_multicast:
            index = interface_index(args.interface)
            if family == socket.AF_INET:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                socket.inet_aton(str(source)))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            else:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, index)
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 1)
        try:
            sock.sendto(payload(args.nonce), endpoint(args.destination_address, args.port,
                                                     args.family, args.interface))
        except OSError as exc:
            if exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENODEV):
                emit(f'NOT_TESTED route/interface unavailable: {exc}')
                return 3
            raise FixtureError(f'Probe send failed: {exc}') from exc
    emit('PAYLOAD_SENT route accepted locally; delivery is not established')
    return 0


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    commands.add_parser('nonce', help='generate a non-secret fixture nonce')

    listener = commands.add_parser('listen', help='run a selected-address UDP receiver')
    listener.add_argument('--family', choices=('ipv4', 'ipv6'), required=True)
    listener.add_argument('--bind-address', required=True)
    listener.add_argument('--port', type=high_port, metavar='PORT', required=True)
    listener.add_argument('--interface')
    listener.add_argument('--multicast-group')
    listener.add_argument('--control-nonce', required=True)
    listener.add_argument('--probe-nonce', required=True)
    listener.add_argument('--control-source-address', required=True)
    listener.add_argument('--probe-source-address', required=True)
    listener.add_argument('--timeout', type=float, default=15.0)

    sender = commands.add_parser('send', help='send one harmless selected-source UDP payload')
    sender.add_argument('--family', choices=('ipv4', 'ipv6'), required=True)
    sender.add_argument('--source-address', required=True)
    sender.add_argument('--destination-address', required=True)
    sender.add_argument('--port', type=high_port, metavar='PORT', required=True)
    sender.add_argument('--interface')
    sender.add_argument('--nonce', required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'nonce':
            print(secrets.token_hex(16))
            return 0
        if os.geteuid() == 0:
            raise FixtureError('Run network fixtures as the normal user, not root.')
        if args.command == 'listen':
            if not 0.25 <= args.timeout <= 300:
                raise FixtureError('Timeout must be between 0.25 and 300 seconds.')
            return run_listener(args)
        return run_sender(args)
    except (FixtureError, OSError) as exc:
        print(f'host-isolation-protocol-fixture: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('host-isolation-protocol-fixture: stopped cleanly', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
