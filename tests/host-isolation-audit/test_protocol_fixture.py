"""Offline tests for the bounded host-isolation UDP fixture."""

import argparse
import errno
import importlib.util
from pathlib import Path
import socket
import threading
import time
import types
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'protocol_fixture', REPO / 'scripts/host-isolation/host-isolation-protocol-fixture.py'
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def listener_args(port, control_nonce, probe_nonce, timeout=0.4):
    return types.SimpleNamespace(
        family='ipv4',
        bind_address='127.0.0.1',
        port=port,
        interface=None,
        multicast_group=None,
        control_nonce=control_nonce,
        probe_nonce=probe_nonce,
        control_source_address='127.0.0.1',
        probe_source_address='127.0.0.2',
        timeout=timeout,
    )


def sender_args(port, nonce, source='127.0.0.1'):
    return types.SimpleNamespace(
        family='ipv4',
        source_address=source,
        destination_address='127.0.0.1',
        port=port,
        interface=None,
        nonce=nonce,
    )


class ProtocolFixtureTests(unittest.TestCase):
    def free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def test_refuses_wildcard_and_short_nonce(self):
        with self.assertRaises(fixture.FixtureError):
            fixture.parse_address('0.0.0.0', 'ipv4')
        with self.assertRaises(fixture.FixtureError):
            fixture.validate_nonce('short')
        with self.assertRaises(argparse.ArgumentTypeError):
            fixture.high_port('53')

    def test_refuses_occupied_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as owner:
            owner.bind(('127.0.0.1', 0))
            args = listener_args(owner.getsockname()[1], 'control-nonce-0001', 'guest-probe-00001')
            with self.assertRaises(fixture.FixtureError):
                fixture.open_listener(args)

    def test_multicast_requires_selected_interface(self):
        args = listener_args(self.free_port(), 'control-nonce-0001', 'guest-probe-00001')
        args.multicast_group = '239.255.0.1'
        with self.assertRaises(fixture.FixtureError):
            fixture.open_listener(args)
        sender = sender_args(self.free_port(), 'control-nonce-0001')
        sender.destination_address = '239.255.0.1'
        with self.assertRaises(fixture.FixtureError):
            fixture.run_sender(sender, lambda message: None)

    def test_missing_route_is_not_tested(self):
        class UnreachableSocket:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def bind(self, unused):
                return None

            def sendto(self, *unused):
                raise OSError(errno.ENETUNREACH, 'fixture route unavailable')

        output = []
        args = sender_args(self.free_port(), 'control-nonce-0001')
        with patch.object(fixture.socket, 'socket', return_value=UnreachableSocket()):
            self.assertEqual(3, fixture.run_sender(args, output.append))
        self.assertTrue(any(line.startswith('NOT_TESTED route/interface unavailable:')
                            for line in output))

    def test_positive_control_and_receiver_non_delivery(self):
        port = self.free_port()
        args = listener_args(port, 'control-nonce-0001', 'guest-probe-00001')
        result = []
        output = []
        worker = threading.Thread(
            target=lambda: result.append(fixture.run_listener(args, output.append))
        )
        worker.start()
        time.sleep(0.05)
        self.assertEqual(0, fixture.run_sender(sender_args(port, args.control_nonce), output.append))
        worker.join(2)
        self.assertEqual([0], result)
        self.assertIn('CONTROL_RECEIVED expected-source', output)
        self.assertIn('RECEIVER_NON_DELIVERY_WITH_CONTROL requires separate ingress/drop attribution',
                      output)

    def test_guest_probe_delivery_fails_fixture(self):
        port = self.free_port()
        args = listener_args(port, 'control-nonce-0001', 'guest-probe-00001')
        result = []
        output = []
        worker = threading.Thread(
            target=lambda: result.append(fixture.run_listener(args, output.append))
        )
        worker.start()
        time.sleep(0.05)
        self.assertEqual(0, fixture.run_sender(sender_args(port, args.control_nonce), output.append))
        self.assertEqual(0, fixture.run_sender(
            sender_args(port, args.probe_nonce, '127.0.0.2'), output.append
        ))
        worker.join(2)
        self.assertEqual([1], result)
        self.assertIn('PROBE_DELIVERED expected-guest-source', output)
        self.assertIn('FAIL probe reached receiver', output)

    def test_missing_positive_control_is_not_tested(self):
        port = self.free_port()
        args = listener_args(port, 'control-nonce-0001', 'guest-probe-00001', timeout=0.25)
        output = []
        self.assertEqual(3, fixture.run_listener(args, output.append))
        self.assertIn('NOT_TESTED positive control was not received', output)


if __name__ == '__main__':
    unittest.main()
