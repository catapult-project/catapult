# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util

# TODO(tonyg): Move webpagereplay.py to a common location.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(), 'chrome', 'test', 'functional')
import webpagereplay  # pylint: disable=F0401

def GetChromeFlags(replay_host, http_port, https_port):
  return webpagereplay.GetChromeFlags(replay_host, http_port, https_port)

class ReplayServer(object):
  def __init__(self, browser_backend, path, is_record_mode, is_append_mode,
               make_javascript_deterministic):
    self._browser_backend = browser_backend
    self._forwarder = None
    self._web_page_replay = None
    self._is_record_mode = is_record_mode
    self._is_append_mode = is_append_mode

    wpr_args = browser_backend.browser_options.extra_wpr_args
    if self._is_record_mode:
      if self._is_append_mode:
        wpr_args.append('--append')
      else:
        wpr_args.append('--record')
    if not make_javascript_deterministic:
      wpr_args.append('--inject_scripts=')
    browser_backend.AddReplayServerOptions(wpr_args)
    self._web_page_replay = webpagereplay.ReplayServer(
        path,
        browser_backend.WEBPAGEREPLAY_HOST,
        browser_backend.wpr_http_port_pair.local_port,
        browser_backend.wpr_https_port_pair.local_port,
        wpr_args)
    # Remove --no-dns_forwarding if it wasn't explicitly requested by backend.
    if '--no-dns_forwarding' not in wpr_args:
      self._web_page_replay.replay_options.remove('--no-dns_forwarding')
    self._web_page_replay.StartServer()

    browser_backend.wpr_http_port_pair.local_port = (
        self._web_page_replay.http_port)
    browser_backend.wpr_http_port_pair.remote_port = (
        browser_backend.wpr_http_port_pair.remote_port or
        self._web_page_replay.http_port)
    browser_backend.wpr_https_port_pair.local_port = (
        self._web_page_replay.https_port)
    browser_backend.wpr_https_port_pair.remote_port = (
        browser_backend.wpr_https_port_pair.remote_port or
        self._web_page_replay.https_port)

    self._forwarder = browser_backend.CreateForwarder(
        browser_backend.wpr_http_port_pair, browser_backend.wpr_https_port_pair)

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
