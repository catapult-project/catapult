# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import forwarders
from telemetry.core import webpagereplay
from telemetry.core import wpr_modes

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
    self._active_replay_args = {}
    self._pending_replay_args = {}
    self._forwarder = None
    self._wpr_server = None

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
    if not archive_path:
      # TODO(slamm, tonyg): Ideally, replay mode should be stopped when there is
      # no archive path. However, if the replay server already started, and
      # a file URL is tested with the
      # telemetry.core.local_server.LocalServerController, then the
      # replay server forwards requests to it. (Chrome is configured to use
      # fixed ports fo all HTTP/HTTPS requests.)
      return
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
          - Input: wpr_port_pairs
          - Output: wpr_port_pairs (browser uses for --testing-fixed-* flags).
    Args:
      browser_backend: instance of telemetry.core.backends.browser_backend
    """
    if not self._pending_replay_args:
      # In some cases (e.g., unit tests), the browser is used without replay.
      return
    if self._pending_replay_args == self._active_replay_args:
      return

    pending_archive_path = self._pending_replay_args['archive_path']



    pending_wpr_mode = self._pending_replay_args['wpr_mode']
    if pending_wpr_mode == wpr_modes.WPR_OFF:
      return
    if (pending_wpr_mode == wpr_modes.WPR_REPLAY and
        not os.path.exists(pending_archive_path)):
      raise ArchiveDoesNotExistError(
          'Archive path does not exist: %s' % pending_archive_path)
    if browser_backend:
      self._browser_backend = browser_backend
      self.StopReplay()  # stop any forwarder too
      wpr_port_pairs = self._browser_backend.wpr_port_pairs
    else:
      # If no browser_backend, then this is an update for an existing browser.
      assert self._browser_backend
      self._StopReplayOnly()  # leave existing forwarder in place
      wpr_port_pairs = self._forwarder.port_pairs
    wpr_http_port = wpr_port_pairs.http.local_port
    wpr_https_port = wpr_port_pairs.https.local_port
    wpr_dns_port = (wpr_port_pairs.dns.local_port
                    if wpr_port_pairs.dns else None)

    archive_path = self._pending_replay_args['archive_path']
    wpr_mode = self._pending_replay_args['wpr_mode']
    netsim = self._pending_replay_args['netsim']
    extra_wpr_args = self._pending_replay_args['extra_wpr_args']
    make_javascript_deterministic = self._pending_replay_args[
        'make_javascript_deterministic']

    if wpr_mode == wpr_modes.WPR_OFF:
      return
    if (wpr_mode == wpr_modes.WPR_REPLAY and
        not os.path.exists(archive_path)):
      raise ArchiveDoesNotExistError(
          'Archive path does not exist: %s' % archive_path)

    wpr_args = _ReplayCommandLineArgs(
        wpr_mode, netsim, extra_wpr_args, make_javascript_deterministic,
        self._platform_backend.wpr_ca_cert_path)
    self._wpr_server = self._ReplayServer(
        archive_path, self._platform_backend.forwarder_factory.host_ip,
        wpr_http_port, wpr_https_port, wpr_dns_port, wpr_args)
    started_ports = self._wpr_server.StartServer()

    if not self._forwarder:
      self._forwarder = self._platform_backend.forwarder_factory.Create(
          _ForwarderPortPairs(started_ports, wpr_port_pairs))

    self._active_replay_args = self._pending_replay_args
    self._pending_replay_args = None

  def _ReplayServer(
      self, archive_path, host_ip, http_port, https_port, dns_port, wpr_args):
    return webpagereplay.ReplayServer(
        archive_path, host_ip, http_port, https_port, dns_port, wpr_args)

  def StopReplay(self):
    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None
    self._StopReplayOnly()

  def _StopReplayOnly(self):
    if self._wpr_server:
      self._wpr_server.StopServer()
      self._wpr_server = None
      self._active_replay_args = {}

  @property
  def wpr_http_device_port(self):
    if not self._forwarder or not self._forwarder.port_pairs.http:
      return None
    return self._forwarder.port_pairs.http.remote_port

  @property
  def wpr_https_device_port(self):
    if not self._forwarder or not self._forwarder.port_pairs.https:
      return None
    return self._forwarder.port_pairs.https.remote_port


def _ReplayCommandLineArgs(wpr_mode, netsim, extra_wpr_args,
                           make_javascript_deterministic, wpr_ca_cert_path):
  wpr_args = list(extra_wpr_args)
  if netsim:
    wpr_args.append('--net=%s' % netsim)
  if wpr_mode == wpr_modes.WPR_APPEND:
    wpr_args.append('--append')
  elif wpr_mode == wpr_modes.WPR_RECORD:
    wpr_args.append('--record')
  if not make_javascript_deterministic:
    wpr_args.append('--inject_scripts=')
  if wpr_ca_cert_path:
    wpr_args.extend([
        '--should_generate_certs',
        '--https_root_ca_cert_path=%s' % wpr_ca_cert_path,
        ])
  return wpr_args


def _ForwarderPortPairs(started_ports, wpr_port_pairs):
  """Return PortPairs with started local ports and requested remote ports.

  The local host is where Telemetry is run. The remote is host where
  the target application is run. The local and remote hosts may be
  the same (e.g., testing a desktop browser) or different (e.g., testing
  an android browser).

  The remote ports may be zero. In that case, the forwarder determines
  the remote ports.

  Args:
    started_ports: a tuple of of integer ports from which to forward:
        (HTTP_PORT, HTTPS_PORT, DNS_PORT)  # DNS_PORT may be None
    wpr_port_pairs: a forwarders.PortPairs instance where the remote ports,
        if set, are used.
  Returns:
    a forwarders.PortPairs instance used to create the forwarder.
  """
  local_http_port, local_https_port, local_dns_port = started_ports
  return forwarders.PortPairs(
      forwarders.PortPair(local_http_port, wpr_port_pairs.http.remote_port),
      forwarders.PortPair(local_https_port, wpr_port_pairs.https.remote_port),
      (forwarders.PortPair(local_dns_port, wpr_port_pairs.dns.remote_port)
       if wpr_port_pairs.dns is not None else None))
