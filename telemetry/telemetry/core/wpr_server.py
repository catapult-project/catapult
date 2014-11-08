# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import forwarders
from telemetry.core import webpagereplay
from telemetry.core import wpr_modes


# TODO(tonyg): Move webpagereplay.py's guts into this class and
# make ReplayServer subclass LocalServer.


class ReplayServer(object):
  def __init__(self, browser_backend, platform_backend, archive_path, wpr_mode,
               netsim, extra_wpr_args, make_javascript_deterministic):
    self._forwarder = None
    self._web_page_replay = None

    wpr_args = list(extra_wpr_args)
    if netsim:
      wpr_args.append('--net=%s' % netsim)
    if wpr_mode == wpr_modes.WPR_APPEND:
      wpr_args.append('--append')
    elif wpr_mode == wpr_modes.WPR_RECORD:
      wpr_args.append('--record')
    if not make_javascript_deterministic:
      wpr_args.append('--inject_scripts=')
    if platform_backend.wpr_ca_cert_path:
      wpr_args.extend([
          '--should_generate_certs',
          '--https_root_ca_cert_path=%s' % platform_backend.wpr_ca_cert_path,
          ])
    self._web_page_replay = webpagereplay.ReplayServer(
        archive_path, browser_backend.forwarder_factory.host_ip,
        browser_backend.wpr_port_pairs.http.local_port,
        browser_backend.wpr_port_pairs.https.local_port,
        (browser_backend.wpr_port_pairs.dns.local_port
         if browser_backend.wpr_port_pairs.dns else None),
        wpr_args)
    started_ports = self._web_page_replay.StartServer()

    # Assign the forwarder port pairs back to the browser_backend.
    #     The port pairs are used to set up the application.
    #     The chrome_browser_backend uses the remote ports to set browser flags.
    port_pairs = self._ForwarderPortPairs(
        started_ports, browser_backend.wpr_port_pairs)
    self._forwarder = browser_backend.forwarder_factory.Create(port_pairs)
    browser_backend.wpr_port_pairs = self._forwarder.port_pairs

  @staticmethod
  def _ForwarderPortPairs(started_ports, wpr_port_pairs):
    """Setup the local and remote forwarding ports.

    The local host is where Telemetry is run. The remote is host where
    the target application is run. The local and remote hosts may be
    the same (e.g., testing a desktop browser) or different (e.g., testing
    an android browser).

    Args:
      started_ports: a tuple of of integer ports from which to forward:
          (HTTP_PORT, HTTPS_PORT, DNS_PORT)  # DNS_PORT may be None
      wpr_port_pairs: a forwaders.PortPairs instance where the remote ports,
          if set, are used.
    Returns:
      a forwarders.PortPairs instance used to create the forwarder.
    """
    local_http_port, local_https_port, local_dns_port = started_ports
    remote_http_port = wpr_port_pairs.http.remote_port
    remote_https_port = wpr_port_pairs.https.remote_port
    http_port_pair = forwarders.PortPair(local_http_port, remote_http_port)
    https_port_pair = forwarders.PortPair(local_https_port, remote_https_port)
    if wpr_port_pairs.dns is None:
      assert not local_dns_port, 'DNS was not requested, but started anyway.'
      dns_port_pair = None
    else:
      assert local_dns_port, 'DNS was requested, but not started.'
      remote_dns_port = wpr_port_pairs.dns.remote_port or local_dns_port
      dns_port_pair = forwarders.PortPair(local_dns_port, remote_dns_port)
    return forwarders.PortPairs(http_port_pair, https_port_pair, dns_port_pair)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def Close(self):
    if self._forwarder:
      self._forwarder.Close()
      self._forwarder = None
    if self._web_page_replay:
      self._web_page_replay.StopServer()
      self._web_page_replay = None
