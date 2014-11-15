# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import tempfile
import unittest

from telemetry.core import wpr_modes
from telemetry.core.platform import network_controller_backend


class FakePlatformBackend(object):
  @property
  def wpr_ca_cert_path(self):
    return None


class FakeBrowserBackend(object):
  pass


class FakeReplayServer(object):
  def __init__(self, browser_backend, platform_backend, **replay_args):
    self.browser_backend = browser_backend
    self.platform_backend = platform_backend
    self.replay_args = replay_args
    self.is_closed = False

  def Close(self):
    assert not self.is_closed
    self.is_closed = True


class TestNetworkControllerBackend(
    network_controller_backend.NetworkControllerBackend):
  """NetworkControllerBackend with a fake ReplayServer."""

  def __init__(self, platform_backend):
    super(TestNetworkControllerBackend, self).__init__(platform_backend)
    self.fake_replay_server = None

  def _ReplayServer(self, browser_backend, platform_backend, replay_args):
    self.fake_replay_server = FakeReplayServer(
        browser_backend, platform_backend, **replay_args)
    return self.fake_replay_server


class NetworkControllerBackendTest(unittest.TestCase):

  def testSameArgsReusesServer(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_file = temp_file.name
      # Create Replay server.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      browser_backend = FakeBrowserBackend()
      b.UpdateReplay(browser_backend)
      self.assertIs(browser_backend, b.fake_replay_server.browser_backend)
      expected_replay_args = dict(
          archive_path=archive_file,
          wpr_mode=wpr_modes.WPR_REPLAY,
          netsim='3g',
          extra_wpr_args=['--some-arg'],
          make_javascript_deterministic=False)
      self.assertEqual(expected_replay_args, b.fake_replay_server.replay_args)

      # Reuse Replay server.
      fake_replay_server = b.fake_replay_server
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      b.UpdateReplay(browser_backend)

    self.assertIs(fake_replay_server, b.fake_replay_server)
    b.StopReplay()
    self.assertTrue(b.fake_replay_server.is_closed)

  def testDifferentArgsUsesDifferentServer(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_file = temp_file.name
      # Create Replay server.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      browser_backend = FakeBrowserBackend()
      b.UpdateReplay(browser_backend)
      self.assertIs(browser_backend, b.fake_replay_server.browser_backend)
      expected_replay_args = dict(
          archive_path=archive_file,
          wpr_mode=wpr_modes.WPR_REPLAY,
          netsim='3g',
          extra_wpr_args=['--some-arg'],
          make_javascript_deterministic=False)
      self.assertEqual(expected_replay_args, b.fake_replay_server.replay_args)
      fake_replay_server = b.fake_replay_server

      # Create different Replay server.
      # Set netsim to None instead of '3g'.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, None, ['--some-arg'])
      b.UpdateReplay(browser_backend)

      self.assertIsNot(fake_replay_server, b.fake_replay_server)
      self.assertTrue(fake_replay_server.is_closed)
      self.assertFalse(b.fake_replay_server.is_closed)
      different_replay_args = dict(
          archive_path=archive_file,
          wpr_mode=wpr_modes.WPR_REPLAY,
          netsim=None,  # first call used '3g'
          extra_wpr_args=['--some-arg'],
          make_javascript_deterministic=False)

    self.assertEqual(different_replay_args, b.fake_replay_server.replay_args)
    b.StopReplay()
    self.assertTrue(b.fake_replay_server.is_closed)

  def testUpdateReplayWithoutArchivePathDoesNotStopReplay(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    with tempfile.NamedTemporaryFile() as temp_file:
      archive_file = temp_file.name
      # Create Replay server.
      b.SetReplayArgs(archive_file, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
      browser_backend = FakeBrowserBackend()
      b.UpdateReplay(browser_backend)
      self.assertFalse(b.fake_replay_server.is_closed)
    b.SetReplayArgs(None, wpr_modes.WPR_REPLAY, '3g', ['--some-arg'])
    b.UpdateReplay()
    self.assertFalse(b.fake_replay_server.is_closed)

  def testUpdateReplayWithoutArgsIsOkay(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    b.UpdateReplay(FakeBrowserBackend())  # does not raise

  def testBadArchivePathRaises(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_REPLAY, '3g', [])
    with self.assertRaises(network_controller_backend.ArchiveDoesNotExistError):
      b.UpdateReplay(FakeBrowserBackend())

  def testBadArchivePathOnRecordIsOkay(self):
    """No ArchiveDoesNotExistError for record mode."""
    b = TestNetworkControllerBackend(FakePlatformBackend())
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_RECORD, '3g', [])
    b.UpdateReplay(FakeBrowserBackend())  # does not raise

  def testModeOffDoesNotCreateReplayServer(self):
    b = TestNetworkControllerBackend(FakePlatformBackend())
    b.SetReplayArgs('/tmp/nonexistant', wpr_modes.WPR_OFF, '3g', [])
    b.UpdateReplay(FakeBrowserBackend())
    self.assertIsNone(b.fake_replay_server)
