# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from telemetry.internal import forwarders
from telemetry.internal.platform import network_controller_backend
from telemetry.util import wpr_modes


DEFAULT_PORTS = forwarders.PortSet(http=1111, https=2222, dns=3333)
FORWARDER_HOST_IP = '123.321.123.321'


class FakePlatformBackend(object):
  def __init__(self):
    self.wpr_ca_cert_path = None
    self.forwarder_factory = FakeForwarderFactory()


class FakeForwarderFactory(object):
  def __init__(self):
    self.host_ip = FORWARDER_HOST_IP

  def Create(self, port_pairs):
    return forwarders.Forwarder(port_pairs)


class FakeReplayServer(object):
  DEFAULT_PORTS = NotImplemented  # Will be assigned during test setUp.

  def __init__(self, archive_path, host_ip, http_port, https_port, dns_port,
               replay_args):
    self.archive_path = archive_path
    self.host_ip = host_ip
    self.ports = forwarders.PortSet(
        http_port or self.DEFAULT_PORTS.http,
        https_port or self.DEFAULT_PORTS.https,
        dns_port or self.DEFAULT_PORTS.dns if dns_port is not None else None)
    self.replay_args = replay_args
    self.is_running = False

  def StartServer(self):
    assert not self.is_running
    self.is_running = True
    return self.ports

  def StopServer(self):
    assert self.is_running
    self.is_running = False


class TestNetworkControllerBackend(
    network_controller_backend.NetworkControllerBackend):
  """Expose some private properties for testing purposes."""

  def SetWprPortPairs(self, http, https, dns):
    self._wpr_port_pairs = forwarders.PortPairs(
        forwarders.PortPair(*http),
        forwarders.PortPair(*https),
        forwarders.PortPair(*dns) if dns is not None else None)

  @property
  def replay_server(self):
    return self._wpr_server

  @property
  def forwarder(self):
    return self._forwarder

  @property
  def platform_backend(self):
    return self._platform_backend


# TODO(perezju): Remove once network_controller_backend is no longer tied to
# the browser_backend.
class FakeBrowserBackend(object):
  def __init__(self):
    # Config to use default ports and no DNS traffic.
    self.wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(0, 0),
        https=forwarders.PortPair(0, 0),
        dns=None)


class NetworkControllerBackendTest(unittest.TestCase):

  def setUp(self):
    # Always use our FakeReplayServer.
    FakeReplayServer.DEFAULT_PORTS = DEFAULT_PORTS  # Use global defaults.
    patcher = mock.patch(
        'telemetry.internal.util.webpagereplay.ReplayServer', FakeReplayServer)
    patcher.start()
    self.addCleanup(patcher.stop)

    # Pretend that only some predefined set of files exist.
    def fake_path_exists(filename):
      return filename in ['some-archive.wpr', 'another-archive.wpr']

    patcher = mock.patch('os.path.exists', side_effect=fake_path_exists)
    self.mock_path_exists = patcher.start()
    self.addCleanup(patcher.stop)

    self.network_controller_backend = TestNetworkControllerBackend(
        FakePlatformBackend())

  def testOpenCloseController(self):
    # TODO(perezju): Add checks for installing/uninstalling test certificates
    # where appropriate.
    b = self.network_controller_backend
    self.assertFalse(b.is_open)
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    self.assertTrue(b.is_open)
    b.Close()
    self.assertFalse(b.is_open)
    b.Close()  # It's fine to close a closed controller.
    self.assertFalse(b.is_open)

  def testOpeningOpenControllerRaises(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    with self.assertRaises(AssertionError):
      b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])

  def testStartStopReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.replay_server.is_running)
    self.assertIsNotNone(b.forwarder.port_pairs)

    old_replay_server = b.replay_server
    old_forwarder = b.forwarder
    b.StopReplay()
    self.assertFalse(old_replay_server.is_running)
    self.assertIsNone(old_forwarder.port_pairs)
    self.assertTrue(b.is_open)  # Controller is still open.

    b.Close()
    self.assertFalse(b.is_open)

  def testClosingControllerAlsoStopsReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.replay_server.is_running)
    self.assertIsNotNone(b.forwarder.port_pairs)

    old_replay_server = b.replay_server
    old_forwarder = b.forwarder
    b.Close()
    self.assertFalse(old_replay_server.is_running)
    self.assertIsNone(old_forwarder.port_pairs)
    self.assertFalse(b.is_open)

  def testReplayOnClosedControllerRaises(self):
    b = self.network_controller_backend
    self.assertFalse(b.is_open)
    with self.assertRaises(AssertionError):
      b.StartReplay('some-archive.wpr')

  def testReplayWithSameArgsReuseServer(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.replay_server.is_running)

    old_replay_server = b.replay_server
    b.StartReplay('some-archive.wpr')
    self.assertIs(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)

  def testReplayWithDifferentArgsUseDifferentServer(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.replay_server.is_running)

    old_replay_server = b.replay_server
    b.StartReplay('another-archive.wpr')
    self.assertIsNot(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)
    self.assertFalse(old_replay_server.is_running)

  def testReplayWithoutArchivePathDoesNotStopReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.replay_server.is_running)
    old_replay_server = b.replay_server

    b.StartReplay(None)
    self.assertIs(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)
    self.assertEqual(b.replay_server.archive_path, 'some-archive.wpr')

  def testModeOffDoesNotCreateReplayServer(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_OFF, '3g', ['--some-arg'])
    b.StartReplay('may-or-may-not-exist.wpr')
    self.assertIsNone(b.replay_server)
    self.assertIsNone(b.forwarder)

  def testBadArchivePathRaises(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    with self.assertRaises(network_controller_backend.ArchiveDoesNotExistError):
      b.StartReplay('does-not-exist.wpr')

  def testBadArchivePathOnRecordIsOkay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_RECORD, '3g', ['--some-arg'])
    b.StartReplay('does-not-exist-yet.wpr')  # Does not raise.

  def testReplayServerSettings(self):
    b = self.network_controller_backend
    b.platform_backend.wpr_ca_cert_path = 'CERT_FILE'
    b.Open(wpr_modes.WPR_RECORD, '3g', ['--some-arg'])
    b.StartReplay('some-archive.wpr')

    # Externally visible properties
    self.assertEqual(b.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.wpr_mode, wpr_modes.WPR_RECORD)
    self.assertEqual(b.wpr_device_ports, DEFAULT_PORTS)

    # Private replay server settings.
    self.assertTrue(b.replay_server.is_running)
    self.assertEqual(b.replay_server.archive_path, 'some-archive.wpr')
    self.assertEqual(b.replay_server.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.replay_server.replay_args, [
        '--some-arg', '--net=3g', '--record', '--inject_scripts=',
        '--should_generate_certs', '--https_root_ca_cert_path=CERT_FILE'])

  def testReplayServerOffSettings(self):
    b = self.network_controller_backend
    b.platform_backend.wpr_ca_cert_path = 'CERT_FILE'
    b.Open(wpr_modes.WPR_OFF, '3g', ['--some-arg'])
    b.StartReplay('some-archive.wpr')

    self.assertEqual(b.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.wpr_mode, wpr_modes.WPR_OFF)
    self.assertEqual(b.wpr_device_ports, None)
    self.assertIsNone(b.replay_server)

  def testUseDefaultPorts(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.SetWprPortPairs(http=(0, 0), https=(0, 0), dns=(0, 0))
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, DEFAULT_PORTS)
    self.assertEqual(b.wpr_device_ports, DEFAULT_PORTS)

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testUseDefaultLocalPorts(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.SetWprPortPairs(http=(0, 8888), https=(0, 4444), dns=(0, 2222))
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, DEFAULT_PORTS)
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(8888, 4444, 2222))

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testUseSpecificPorts(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.SetWprPortPairs(http=(88, 8888), https=(44, 4444), dns=None)
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, forwarders.PortSet(88, 44, None))
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(8888, 4444, None))

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testDefaultPortsMayChange(self):
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(123, 456, 789)
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.SetWprPortPairs(http=(0, 0), https=(0, 0), dns=(0, 0))
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(123, 456, 789))

    # If replay restarts, use a different set of default ports.
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(987, 654, 321)
    b.StartReplay('another-archive.wpr')
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(987, 654, 321))

  # TODO(perezju): Remove when old API is gone.
  def testUpdateReplayWithoutArgsIsOkay(self):
    b = self.network_controller_backend
    b.UpdateReplay(FakeBrowserBackend())  # Does not raise.

  # TODO(perezju): Remove when old API is gone.
  def testSameBrowserUsesSamePorts(self):
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(222, 444, 555)
    b = self.network_controller_backend
    b.SetReplayArgs('some-archive.wpr', wpr_modes.WPR_REPLAY, '3g', [])
    b.UpdateReplay(FakeBrowserBackend())
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(222, 444, None))

    # If replay restarts, use a different set of default ports.
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(987, 654, 321)

    old_replay_server = b.replay_server
    b.SetReplayArgs('another-archive.wpr', wpr_modes.WPR_REPLAY, None, [])
    b.UpdateReplay()  # No browser backend means use the previous one.

    # Even though WPR is restarted, it uses the same ports because
    # the browser was configured to a particular port set.
    self.assertIsNot(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)
    self.assertFalse(old_replay_server.is_running)
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(222, 444, None))
