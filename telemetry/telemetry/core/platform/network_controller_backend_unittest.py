# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import tempfile
import unittest

from telemetry.core import forwarders
from telemetry.core.platform import network_controller_backend
from telemetry.core import wpr_modes


class FakePlatformBackend(object):
  @property
  def wpr_ca_cert_path(self):
    return None

  @property
  def forwarder_factory(self):
    return FakeForwarderFactory()


class FakeForwarderFactory(object):
  def __init__(self):
    self.host_ip = '123.321.123.321'
    self.port_pairs = None

  def Create(self, port_pairs):
    return forwarders.Forwarder(port_pairs)


class FakeBrowserBackend(object):
  def __init__(self, http_ports, https_ports, dns_ports):
    self.wpr_port_pairs = forwarders.PortPairs(
      http=forwarders.PortPair(*http_ports),
      https=forwarders.PortPair(*https_ports),
      dns=forwarders.PortPair(*dns_ports) if dns_ports else None)


class FakeReplayServer(object):
  def __init__(self, archive_path, host_ip, http_port, https_port, dns_port,
               replay_args):
    self.archive_path = archive_path
    self.host_ip = host_ip
    self.http_port = http_port
    self.https_port = https_port
    self.dns_port = dns_port
    self.replay_args = replay_args
    self.is_stopped = False

  def StartServer(self):
    return self.http_port, self.https_port, self.dns_port

  def StopServer(self):
    assert not self.is_stopped
    self.is_stopped = True


class TestNetworkControllerBackend(
    network_controller_backend.NetworkControllerBackend):
  """NetworkControllerBackend with a fake ReplayServer."""

  def __init__(self, platform_backend, fake_started_http_port,
               fake_started_https_port, fake_started_dns_port):
    super(TestNetworkControllerBackend, self).__init__(platform_backend)
    self.fake_started_http_port = fake_started_http_port
    self.fake_started_https_port = fake_started_https_port
    self.fake_started_dns_port = fake_started_dns_port
    self.fake_replay_server = None

  def _ReplayServer(self, archive_path, host_ip, http_port, https_port,
                    dns_port, replay_args):
    http_port = http_port or self.fake_started_http_port
    https_port = https_port or self.fake_started_https_port
    dns_port = (None if dns_port is None else
                (dns_port or self.fake_started_dns_port))
    self.fake_replay_server = FakeReplayServer(
        archive_path, host_ip, http_port, https_port, dns_port, replay_args)
    return self.fake_replay_server


class NetworkControllerBackendTest(unittest.TestCase):

  def setUp(self):
    self.browser_backend = FakeBrowserBackend(
        http_ports=(0, 0),
        https_ports=(0, 0),
        dns_ports=None)
    self.network_controller_backend = TestNetworkControllerBackend(
        FakePlatformBackend(),
        fake_started_http_port=222,
        fake_started_https_port=444,
        fake_started_dns_port=None)

  def testSameArgsReuseServer(self):
    b = self.network_controller_backend
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_path = temp_file.name

      # Create Replay server.
      b.SetReplayArgs(archive_path, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      b.UpdateReplay(self.browser_backend)

      self.assertEqual(archive_path, b.fake_replay_server.archive_path)
      self.assertEqual('123.321.123.321', b.fake_replay_server.host_ip)
      self.assertEqual(
        ['--some-arg', '--net=3g', '--inject_scripts='],
        b.fake_replay_server.replay_args)
      self.assertEqual(222, b.wpr_http_device_port)
      self.assertEqual(444, b.wpr_https_device_port)

      # Reuse Replay server.
      fake_replay_server = b.fake_replay_server
      b.SetReplayArgs(archive_path, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      b.UpdateReplay(self.browser_backend)

    self.assertIs(fake_replay_server, b.fake_replay_server)
    b.StopReplay()
    self.assertTrue(b.fake_replay_server.is_stopped)

  def testDifferentArgsUseDifferentServer(self):
    b = self.network_controller_backend
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_file = temp_file.name

      # Create Replay server.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      b.UpdateReplay(self.browser_backend)

      self.assertEqual(
        ['--some-arg', '--net=3g', '--inject_scripts='],
        b.fake_replay_server.replay_args)
      self.assertEqual(222, b.wpr_http_device_port)
      self.assertEqual(444, b.wpr_https_device_port)

      # If Replay restarts, it uses these ports when passed "0" for ports.
      b.fake_started_http_port = 212
      b.fake_started_https_port = 323
      b.fake_started_dns_port = None

      # Create different Replay server (set netsim to None instead of 3g).
      fake_replay_server = b.fake_replay_server
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, None, ['--some-arg'])
      b.UpdateReplay(self.browser_backend)

      self.assertIsNot(fake_replay_server, b.fake_replay_server)
      self.assertTrue(fake_replay_server.is_stopped)
      self.assertFalse(b.fake_replay_server.is_stopped)

    self.assertEqual(
      ['--some-arg', '--inject_scripts='],
      b.fake_replay_server.replay_args)
    self.assertEqual(212, b.wpr_http_device_port)
    self.assertEqual(323, b.wpr_https_device_port)
    b.StopReplay()
    self.assertTrue(b.fake_replay_server.is_stopped)

  def testUpdateReplayWithoutArchivePathDoesNotStopReplay(self):
    b = TestNetworkControllerBackend(
        FakePlatformBackend(),
        fake_started_http_port=222,
        fake_started_https_port=444,
        fake_started_dns_port=None)
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_file = temp_file.name
      # Create Replay server.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      browser_backend = FakeBrowserBackend(
        http_ports=(0, 0), https_ports=(0, 0), dns_ports=None)
      b.UpdateReplay(browser_backend)
      self.assertFalse(b.fake_replay_server.is_stopped)
    b.SetReplayArgs(None, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.UpdateReplay()
    self.assertFalse(b.fake_replay_server.is_stopped)

  def testUpdateReplayWithoutArgsIsOkay(self):
    b = self.network_controller_backend
    b.UpdateReplay(self.browser_backend)  # does not raise

  def testBadArchivePathRaises(self):
    b = self.network_controller_backend
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_REPLAY, '3g', [])
    with self.assertRaises(network_controller_backend.ArchiveDoesNotExistError):
      b.UpdateReplay(self.browser_backend)

  def testBadArchivePathOnRecordIsOkay(self):
    """No ArchiveDoesNotExistError for record mode."""
    b = self.network_controller_backend
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_RECORD, '3g', [])
    b.UpdateReplay(self.browser_backend)  # does not raise

  def testModeOffDoesNotCreateReplayServer(self):
    b = self.network_controller_backend
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_OFF, '3g', [])
    b.UpdateReplay(self.browser_backend)
    self.assertIsNone(b.fake_replay_server)

  def testSameBrowserUsesSamePorts(self):
    b = self.network_controller_backend
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_path = temp_file.name

      # Create Replay server.
      b.SetReplayArgs(archive_path, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      b.UpdateReplay(self.browser_backend)

      self.assertEqual(archive_path, b.fake_replay_server.archive_path)
      self.assertEqual('123.321.123.321', b.fake_replay_server.host_ip)
      self.assertEqual(
        ['--some-arg', '--net=3g', '--inject_scripts='],
        b.fake_replay_server.replay_args)
      self.assertEqual(222, b.wpr_http_device_port)
      self.assertEqual(444, b.wpr_https_device_port)

      # If Replay restarts, it uses these ports when passed "0" for ports.
      b.fake_started_http_port = 212
      b.fake_started_https_port = 434
      b.fake_started_dns_port = None

      # Reuse Replay server.
      fake_replay_server = b.fake_replay_server
      b.SetReplayArgs(archive_path, wpr_modes.WPR_REPLAY, None, ['--NEW-ARG'])
      b.UpdateReplay()  # no browser backend means use the previous one

    # Even though WPR is restarted, it uses the same ports because
    # the browser was configured to a particular port set.
    self.assertIsNot(fake_replay_server, b.fake_replay_server)
    self.assertEqual(222, b.wpr_http_device_port)
    self.assertEqual(444, b.wpr_https_device_port)
    b.StopReplay()
    self.assertTrue(b.fake_replay_server.is_stopped)

# pylint: disable=W0212
class ForwarderPortPairsTest(unittest.TestCase):
  def testZeroIsOkayForRemotePorts(self):
    started_ports = (8080, 8443, None)
    wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(0, 0),
        https=forwarders.PortPair(0, 0),
        dns=None)
    expected_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(8080, 0),
        https=forwarders.PortPair(8443, 0),
        dns=None)
    self.assertEqual(
        expected_port_pairs,
        network_controller_backend._ForwarderPortPairs(started_ports,
                                                       wpr_port_pairs))

  def testCombineStartedAndRemotePorts(self):
    started_ports = (8888, 4343, 5353)
    wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(0, 80),
        https=forwarders.PortPair(0, 443),
        dns=forwarders.PortPair(0, 53))
    expected_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(8888, 80),
        https=forwarders.PortPair(4343, 443),
        dns=forwarders.PortPair(5353, 53))
    self.assertEqual(
        expected_port_pairs,
        network_controller_backend._ForwarderPortPairs(started_ports,
                                                       wpr_port_pairs))
