# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from telemetry.internal.util import wpr_server
from telemetry.internal.util import webpagereplay_go_server
from telemetry.internal.util import ts_proxy_server
from telemetry.util import wpr_modes


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
    self._wpr_mode = None
    self._extra_wpr_args = None
    self._use_wpr_go = False
    self._archive_path = None
    self._make_javascript_deterministic = None
    self._forwarder = None
    self._is_test_ca_installed = None
    self._wpr_server = None
    self._ts_proxy_server = None
    self._port_pair = None
    self._use_live_traffic = None

  def InitializeIfNeeded(self, use_live_traffic):
    """
    This may, e.g., install test certificates and perform any needed setup
    on the target platform.

    After network interactions are over, clients should call the Close method.
    """
    if self._use_live_traffic is None:
      self._use_live_traffic = use_live_traffic
    assert self._use_live_traffic == use_live_traffic, (
        'inconsistent state of use_live_traffic')
    assert bool(self._ts_proxy_server) == bool(self._forwarder)
    if self._ts_proxy_server:
      return
    local_port = self._StartTsProxyServer(self._use_live_traffic)
    self._forwarder = self._platform_backend.forwarder_factory.Create(
        self._platform_backend.GetPortPairForForwarding(local_port))

  @property
  def is_open(self):
    return self._wpr_mode is not None

  @property
  def is_initialized(self):
    return self._forwarder is not None

  @property
  def host_ip(self):
    return self._platform_backend.forwarder_factory.host_ip

  @property
  def wpr_device_ports(self):
    try:
      return self._forwarder.port_pairs.remote_ports
    except AttributeError:
      return None

  def Open(self, wpr_mode, extra_wpr_args, use_wpr_go=False):
    """Configure and prepare target platform for network control.

    This may, e.g., install test certificates and perform any needed setup
    on the target platform.

    After network interactions are over, clients should call the Close method.

    Args:
      wpr_mode: a mode for web page replay; available modes are
          wpr_modes.WPR_OFF, wpr_modes.APPEND, wpr_modes.WPR_REPLAY, or
          wpr_modes.WPR_RECORD.
      extra_wpr_args: an list of extra arguments for web page replay.
    """
    assert not self.is_open, 'Network controller is already open'
    self._wpr_mode = wpr_mode
    self._extra_wpr_args = extra_wpr_args
    self._use_wpr_go = use_wpr_go
    self._InstallTestCa()

  def Close(self):
    """Undo changes in the target platform used for network control.

    Implicitly stops replay if currently active.
    """
    self.StopReplay()
    self._StopForwarder()
    self._StopTsProxyServer()
    self._RemoveTestCa()
    self._make_javascript_deterministic = None
    self._archive_path = None
    self._extra_wpr_args = None
    self._use_wpr_go = False
    self._wpr_mode = None

  def _InstallTestCa(self):
    if not self._platform_backend.supports_test_ca or not self._use_wpr_go:
      return
    try:
      self._platform_backend.InstallTestCa()
      logging.info('Test certificate authority installed on target platform.')
    except Exception: # pylint: disable=broad-except
      logging.exception(
          'Failed to install test certificate authority on target platform. '
          'Browsers may fall back to ignoring certificate errors.')
      self._RemoveTestCa()

  @property
  def is_test_ca_installed(self):
    return self._is_test_ca_installed

  def _RemoveTestCa(self):
    if not self._is_test_ca_installed:
      return
    try:
      self._platform_backend.RemoveTestCa()
    except Exception: # pylint: disable=broad-except
      # Best effort cleanup - show the error and continue.
      logging.exception(
          'Error trying to remove certificate authority from target platform.')
    finally:
      self._is_test_ca_installed = False

  def StartReplay(self, archive_path, make_javascript_deterministic=False):
    """Start web page replay from a given replay archive.

    Starts as needed, and reuses if possible, the replay server on the host and
    a forwarder from the host to the target platform.

    Implementation details
    ----------------------

    The local host is where Telemetry is run. The remote is host where
    the target application is run. The local and remote hosts may be
    the same (e.g., testing a desktop browser) or different (e.g., testing
    an android browser).

    A replay server is started on the local host using the local ports, while
    a forwarder ties the local to the remote ports.

    Both local and remote ports may be zero. In that case they are determined
    by the replay server and the forwarder respectively. Setting dns to None
    disables DNS traffic.

    Args:
      archive_path: a path to a specific WPR archive.
      make_javascript_deterministic: True if replay should inject a script
          to make JavaScript behave deterministically (e.g., override Date()).
    """
    assert self.is_open, 'Network controller is not open'
    if self._wpr_mode == wpr_modes.WPR_OFF:
      return
    if not archive_path:
      # TODO(slamm, tonyg): Ideally, replay mode should be stopped when there is
      # no archive path. However, if the replay server already started, and
      # a file URL is tested with the
      # telemetry.core.local_server.LocalServerController, then the
      # replay server forwards requests to it. (Chrome is configured to use
      # fixed ports fo all HTTP/HTTPS requests.)
      return
    if (self._wpr_mode == wpr_modes.WPR_REPLAY and
        not os.path.exists(archive_path)):
      raise ArchiveDoesNotExistError(
          'Archive path does not exist: %s' % archive_path)
    if (self._wpr_server is not None and
        self._archive_path == archive_path and
        self._make_javascript_deterministic == make_javascript_deterministic):
      return  # We may reuse the existing replay server.

    self._archive_path = archive_path
    self._make_javascript_deterministic = make_javascript_deterministic
    local_ports = self._StartReplayServer()
    self._ts_proxy_server.UpdateOutboundPorts(
        http_port=local_ports.http, https_port=local_ports.https)

  def _StopForwarder(self):
    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None

  def StopReplay(self):
    """Stop web page replay.

    Stops both the replay server and the forwarder if currently active.
    """
    self._StopReplayServer()

  def _StartReplayServer(self):
    """Start the replay server and return the started local_ports."""
    self._StopReplayServer()  # In case it was already running.
    if self._use_wpr_go:
      self._wpr_server = webpagereplay_go_server.ReplayServer(
          self._archive_path,
          self.host_ip,
          http_port=0,
          https_port=0,
          replay_options=self._ReplayCommandLineArgs())
    else:
      self._wpr_server = wpr_server.ReplayServer(
          self._archive_path,
          self.host_ip,
          http_port=0,
          https_port=0,
          dns_port=None,
          replay_options=self._ReplayCommandLineArgs())
    return self._wpr_server.StartServer()

  def _StopReplayServer(self):
    """Stop the replay server only."""
    if self._wpr_server:
      self._wpr_server.StopServer()
      self._wpr_server = None

  def _StopTsProxyServer(self):
    """Stop the replay server only."""
    if self._ts_proxy_server:
      self._ts_proxy_server.StopServer()
      self._ts_proxy_server = None

  def _ReplayCommandLineArgs(self):
    wpr_args = list(self._extra_wpr_args)
    if self._wpr_mode == wpr_modes.WPR_APPEND:
      wpr_args.append('--append')
    elif self._wpr_mode == wpr_modes.WPR_RECORD:
      wpr_args.append('--record')
    if not self._make_javascript_deterministic:
      wpr_args.append('--inject_scripts=')
    return wpr_args

  def _StartTsProxyServer(self, use_live_traffic):
    assert not self._ts_proxy_server, 'ts_proxy_server is already started'
    host_ip = None
    if not use_live_traffic:
      host_ip = self.host_ip
    self._ts_proxy_server = ts_proxy_server.TsProxyServer(host_ip=host_ip)
    self._ts_proxy_server.StartServer()
    return self._ts_proxy_server.port

  @property
  def forwarder(self):
    return self._forwarder

  @property
  def ts_proxy_server(self):
    return self._ts_proxy_server
