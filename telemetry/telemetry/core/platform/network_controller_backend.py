# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import wpr_modes
from telemetry.core import wpr_server


class ArchiveDoesNotExistError(Exception):
  """Raised when the archive path does not exist for replay mode."""
  pass


class ReplayAndBrowserPortsError(Exception):
  """Raised an existing browser would get different remote replay ports."""
  pass


class NetworkControllerBackend(object):
  """Control network settings and servers to simulate the Web.

  Network changes include forwarding device ports to host platform ports.
  Web Page Replay is used to record and replay HTTP/HTTPS responses.
  """

  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._browser_backend = None
    self._wpr_server = None
    self._active_replay_args = {}
    self._pending_replay_args = {}

  def SetReplayArgs(self, archive_path, wpr_mode, netsim, extra_wpr_args,
                    make_javascript_deterministic=False):
    """Save the arguments needed for replay.

    To make the settings effective, this call must be followed by a call
    to UpdateReplay.

    Args:
      archive_path: a path to a specific WPR archive.
      wpr_mode: one of wpr_modes.WPR_OFF, wpr_modes.WPR_APPEND,
          wpr_modes.WPR_REPLAY, or wpr_modes.WPR_RECORD.
      netsim: a net_config string ('dialup', '3g', 'dsl', 'cable', or 'fios').
      extra_wpr_args: a list of addtional replay args (or an empty list).
      make_javascript_deterministic: True if replay should inject a script
          to make JavaScript behave deterministically (e.g., override Date()).
    """
    self._pending_replay_args = dict(
        archive_path=archive_path,
        wpr_mode=wpr_mode,
        netsim=netsim,
        extra_wpr_args=extra_wpr_args,
        make_javascript_deterministic=make_javascript_deterministic)
    # TODO(slamm): Update replay here when the browser_backend dependencies
    # are moved to the platform. https://crbug.com/423962
    # |self._pending_replay_args| can be removed at that time.

  def UpdateReplay(self, browser_backend=None):
    """Start or reuse Web Page Replay.

    UpdateReplay must be called after every call to SetReplayArgs.

    TODO(slamm): Update replay in SetReplayArgs once the browser_backend
        dependencies move to platform. https://crbug.com/423962
        browser_backend properties used:
          - Input: forwarder_factory, wpr_port_pairs, wpr_ca_cert_path
          - Output: wpr_port_pairs (browser uses for --testing-fixed-* flags).
    Args:
      browser_backend: instance of telemetry.core.backends.browser_backend
    """
    if not self._pending_replay_args:
      # In some cases (e.g., unit tests), the browser is used without replay.
      return
    if self._pending_replay_args == self._active_replay_args:
      return

    self.StopReplay()

    pending_archive_path = self._pending_replay_args['archive_path']
    pending_wpr_mode = self._pending_replay_args['wpr_mode']
    if not pending_archive_path or pending_wpr_mode == wpr_modes.WPR_OFF:
      return
    if (pending_wpr_mode == wpr_modes.WPR_REPLAY and
        not os.path.exists(pending_archive_path)):
      raise ArchiveDoesNotExistError(
          'Archive path does not exist: %s' % pending_archive_path)
    if browser_backend:
      self._browser_backend = browser_backend
    else:
      # If no browser_backend, then this is an update for an existing wpr.
      assert self._browser_backend
    self._wpr_server = self._ReplayServer(
        self._browser_backend, self._pending_replay_args)
    self._active_replay_args = self._pending_replay_args
    self._pending_replay_args = None

  def _ReplayServer(self, browser_backend, replay_args):
    return wpr_server.ReplayServer(browser_backend, **replay_args)

  def StopReplay(self):
    if self._wpr_server:
      self._wpr_server.Close()
      self._wpr_server = None
      self._active_replay_args = {}
