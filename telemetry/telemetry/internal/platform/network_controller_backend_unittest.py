# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import mock
import unittest

from telemetry.internal import forwarders
from telemetry.internal.platform import network_controller_backend
from telemetry.util import wpr_modes


DEFAULT_PORTS = forwarders.PortSet(http=1111, https=2222, dns=3333)
FORWARDER_HOST_IP = '123.321.123.321'
EXPECTED_WPR_CA_CERT_PATH = os.path.join('[tempdir]', 'testca.pem')


class FakePlatformBackend(object):
  def __init__(self):
    self.forwarder_factory = FakeForwarderFactory()
    self.supports_test_ca = True
    self.is_test_ca_installed = False
    self.faulty_cert_installer = False
    self.wpr_port_pairs = None
    # Normally test using all default ports.
    self.SetWprPortPairs(http=(0, 0), https=(0, 0), dns=(0, 0))

  def SetWprPortPairs(self, http, https, dns):
    self.wpr_port_pairs = forwarders.PortPairs(
        forwarders.PortPair(*http),
        forwarders.PortPair(*https),
        forwarders.PortPair(*dns) if dns is not None else None)

  def GetWprPortPairs(self):
    return self.wpr_port_pairs

  def InstallTestCa(self, ca_cert_path):
    del ca_cert_path  # Unused argument.
    self.is_test_ca_installed = True
    # Exception is raised after setting the "installed" value to confirm that
    # cleaup code is being called in case of errors.
    if self.faulty_cert_installer:
      raise Exception('Cert install failed!')

  def RemoveTestCa(self):
    self.is_test_ca_installed = False


class FakeForwarderFactory(object):
  def __init__(self):
    self.host_ip = FORWARDER_HOST_IP

  def Create(self, port_pairs):
    return forwarders.Forwarder(
        forwarders.PortPairs(*[
            forwarders.PortPair(p.local_port, p.remote_port or p.local_port)
            if p else None for p in port_pairs]))


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

  @property
  def wpr_ca_cert_path(self):
    return self._wpr_ca_cert_path

  @property
  def replay_server(self):
    return self._wpr_server

  @property
  def forwarder(self):
    return self._forwarder

  @property
  def platform_backend(self):
    return self._platform_backend


# pylint: disable=no-member
class NetworkControllerBackendTest(unittest.TestCase):
  def Patch(self, *args, **kwargs):
    """Patch an object for the duration of a test, and return its mock."""
    patcher = mock.patch(*args, **kwargs)
    mock_object = patcher.start()
    self.addCleanup(patcher.stop)
    return mock_object

  def PatchImportedModule(self, name):
    """Shorthand to patch a module imported by network_controller_backend."""
    return self.Patch(
        'telemetry.internal.platform.network_controller_backend.%s' % name)

  def setUp(self):
    # Always use our FakeReplayServer.
    FakeReplayServer.DEFAULT_PORTS = DEFAULT_PORTS  # Use global defaults.
    self.Patch(
        'telemetry.internal.util.webpagereplay.ReplayServer', FakeReplayServer)

    # Pretend that only some predefined set of files exist.
    def fake_path_exists(filename):
      return filename in ['some-archive.wpr', 'another-archive.wpr']

    self.Patch('os.path.exists', side_effect=fake_path_exists)

    # Mock some imported modules.
    mock_certutils = self.PatchImportedModule('certutils')
    mock_certutils.openssl_import_error = None
    mock_certutils.generate_dummy_ca_cert.return_value = ('-', '-')

    mock_platformsettings = self.PatchImportedModule('platformsettings')
    mock_platformsettings.HasSniSupport.return_value = True

    mock_tempfile = self.PatchImportedModule('tempfile')
    mock_tempfile.mkdtemp.return_value = '[tempdir]'

    self.PatchImportedModule('shutil')

    self.network_controller_backend = TestNetworkControllerBackend(
        FakePlatformBackend())

  def testOpenCloseController(self):
    b = self.network_controller_backend
    self.assertFalse(b.is_open)
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg']) # Also installs test CA.
    self.assertTrue(b.is_open)
    self.assertTrue(b.is_test_ca_installed)
    self.assertTrue(b.platform_backend.is_test_ca_installed)
    b.Close() # Also removes test CA.
    self.assertFalse(b.is_open)
    self.assertFalse(b.is_test_ca_installed)
    self.assertFalse(b.platform_backend.is_test_ca_installed)
    b.Close()  # It's fine to close a closed controller.
    self.assertFalse(b.is_open)

  def testOpeningOpenControllerRaises(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    with self.assertRaises(AssertionError):
      b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])

  def testInstallTestCaFailure(self):
    b = self.network_controller_backend
    b.platform_backend.faulty_cert_installer = True
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg']) # Try to install test CA.

    # Test CA is not installed, but the controller is otherwise open and safe
    # to use.
    self.assertTrue(b.is_open)
    self.assertFalse(b.is_test_ca_installed)
    self.assertFalse(b.platform_backend.is_test_ca_installed)
    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)

    b.Close() # No test CA to remove.
    self.assertFalse(b.is_open)
    self.assertFalse(b.is_test_ca_installed)
    self.assertFalse(b.platform_backend.is_test_ca_installed)

  def testStartStopReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    self.assertFalse(b.is_replay_active)

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertTrue(b.replay_server.is_running)
    self.assertIsNotNone(b.forwarder.port_pairs)

    old_replay_server = b.replay_server
    old_forwarder = b.forwarder
    b.StopReplay()
    self.assertFalse(b.is_replay_active)
    self.assertFalse(old_replay_server.is_running)
    self.assertIsNone(old_forwarder.port_pairs)
    self.assertTrue(b.is_open)  # Controller is still open.

    b.Close()
    self.assertFalse(b.is_open)

  def testClosingControllerAlsoStopsReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertTrue(b.replay_server.is_running)
    self.assertIsNotNone(b.forwarder.port_pairs)

    old_replay_server = b.replay_server
    old_forwarder = b.forwarder
    b.Close()
    self.assertFalse(b.is_replay_active)
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
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertTrue(b.replay_server.is_running)

    old_replay_server = b.replay_server
    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertIs(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)

  def testReplayWithDifferentArgsUseDifferentServer(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertTrue(b.replay_server.is_running)

    old_replay_server = b.replay_server
    b.StartReplay('another-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertIsNot(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)
    self.assertFalse(old_replay_server.is_running)

  def testReplayWithoutArchivePathDoesNotStopReplay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])

    b.StartReplay('some-archive.wpr')
    self.assertTrue(b.is_replay_active)
    self.assertTrue(b.replay_server.is_running)
    old_replay_server = b.replay_server

    b.StartReplay(None)
    self.assertTrue(b.is_replay_active)
    self.assertIs(b.replay_server, old_replay_server)
    self.assertTrue(b.replay_server.is_running)
    self.assertEqual(b.replay_server.archive_path, 'some-archive.wpr')

  def testModeOffDoesNotCreateReplayServer(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_OFF, ['--some-arg'])
    b.StartReplay('may-or-may-not-exist.wpr')
    self.assertFalse(b.is_replay_active)
    self.assertIsNone(b.replay_server)
    self.assertIsNone(b.forwarder)

  def testBadArchivePathRaises(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    with self.assertRaises(network_controller_backend.ArchiveDoesNotExistError):
      b.StartReplay('does-not-exist.wpr')

  def testBadArchivePathOnRecordIsOkay(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_RECORD, ['--some-arg'])
    b.StartReplay('does-not-exist-yet.wpr')  # Does not raise.
    self.assertTrue(b.is_replay_active)

  def testReplayServerSettings(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_RECORD, ['--some-arg'])
    b.StartReplay('some-archive.wpr')

    # Externally visible properties
    self.assertTrue(b.is_replay_active)
    self.assertEqual(b.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.wpr_device_ports, DEFAULT_PORTS)

    # Private replay server settings.
    self.assertTrue(b.replay_server.is_running)
    self.assertEqual(b.replay_server.archive_path, 'some-archive.wpr')
    self.assertEqual(b.replay_server.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.replay_server.replay_args, [
        '--some-arg', '--record', '--inject_scripts=',
        '--should_generate_certs',
        '--https_root_ca_cert_path=%s' % EXPECTED_WPR_CA_CERT_PATH])

  def testReplayServerOffSettings(self):
    b = self.network_controller_backend
    b.platform_backend.wpr_ca_cert_path = 'CERT_FILE'
    b.Open(wpr_modes.WPR_OFF, ['--some-arg'])
    b.StartReplay('some-archive.wpr')

    self.assertFalse(b.is_replay_active)
    self.assertEqual(b.host_ip, FORWARDER_HOST_IP)
    self.assertEqual(b.wpr_device_ports, None)
    self.assertIsNone(b.replay_server)

  def testUseDefaultPorts(self):
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, DEFAULT_PORTS)
    self.assertEqual(b.wpr_device_ports, DEFAULT_PORTS)

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testUseDefaultLocalPorts(self):
    b = self.network_controller_backend
    b.platform_backend.SetWprPortPairs(
        http=(0, 8888), https=(0, 4444), dns=(0, 2222))
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, DEFAULT_PORTS)
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(8888, 4444, 2222))

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testUseSpecificPorts(self):
    b = self.network_controller_backend
    b.platform_backend.SetWprPortPairs(
        http=(88, 8888), https=(44, 4444), dns=None)
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.replay_server.ports, forwarders.PortSet(88, 44, None))
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(8888, 4444, None))

    # Invariant
    self.assertEqual(b.forwarder.port_pairs.local_ports, b.replay_server.ports)
    self.assertEqual(b.forwarder.port_pairs.remote_ports, b.wpr_device_ports)

  def testRestartReplayShouldReusePorts(self):
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(123, 456, 789)
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(123, 456, 789))

    # If replay restarts, the factory may use a different set of default ports.
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(987, 654, 321)
    b.StartReplay('another-archive.wpr')

    # However same ports must be used, because apps/browsers may already be
    # configured to use the old set of ports.
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(123, 456, 789))

  def testNewControllerSessionMayUseDifferentPorts(self):
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(123, 456, 789)
    b = self.network_controller_backend
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(123, 456, 789))
    b.Close()

    # If replay restarts, the factory may use a different set of default ports.
    FakeReplayServer.DEFAULT_PORTS = forwarders.PortSet(987, 654, 321)
    b.Open(wpr_modes.WPR_REPLAY, ['--some-arg'])
    b.StartReplay('some-archive.wpr')

    # This time the network controller session was closed between replay's,
    # so it's fine to use a different set of ports.
    self.assertEqual(b.wpr_device_ports, forwarders.PortSet(987, 654, 321))
