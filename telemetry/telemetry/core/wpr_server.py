# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util

# TODO(tonyg): Move webpagereplay.py to a common location.
util.AddDirToPythonPath(
    util.GetChromiumSrcDir(), 'chrome', 'test', 'functional')
import webpagereplay  # pylint: disable=F0401

def GetChromeFlags(replay_host, http_port, https_port):
  return webpagereplay.GetChromeFlags(replay_host, http_port, https_port)

class ReplayServer(object):
  def __init__(self, browser_backend, archive_path, is_record_mode,
               is_append_mode, make_javascript_deterministic, inject_scripts):
    self._browser_backend = browser_backend
    self._archive_path = archive_path
    self._is_record_mode = is_record_mode
    self._is_append_mode = is_append_mode
    self._make_javascript_deterministic = make_javascript_deterministic
    self._inject_scripts = inject_scripts
    self._forwarder = None
    self._web_page_replay = None

    self._forwarder = browser_backend.CreateForwarder(
        util.PortPair(browser_backend.webpagereplay_local_http_port,
                      browser_backend.webpagereplay_remote_http_port),
        util.PortPair(browser_backend.webpagereplay_local_https_port,
                      browser_backend.webpagereplay_remote_https_port))

    wpr_args = browser_backend.browser_options.extra_wpr_args
    if self._is_record_mode:
      if self._is_append_mode:
        wpr_args.append('--append')
      else:
        wpr_args.append('--record')
    if make_javascript_deterministic:
      scripts = [os.path.join(util.GetChromiumSrcDir(), 'third_party',
                              'webpagereplay', 'deterministic.js')]
    else:
      scripts = []
    if self._inject_scripts:
      scripts.extend(self._inject_scripts)
    scripts = [os.path.abspath(p) for p in scripts]
    wpr_args.append('--inject_scripts=%s' % (','.join(scripts)))
    browser_backend.AddReplayServerOptions(wpr_args)
    self._web_page_replay = webpagereplay.ReplayServer(
        self._archive_path,
        browser_backend.WEBPAGEREPLAY_HOST,
        browser_backend.webpagereplay_local_http_port,
        browser_backend.webpagereplay_local_https_port,
        wpr_args)
    # Remove --no-dns_forwarding if it wasn't explicitly requested by backend.
    if '--no-dns_forwarding' not in wpr_args:
      self._web_page_replay.replay_options.remove('--no-dns_forwarding')
    self._web_page_replay.StartServer()

  @property
  def archive_path(self):
    return self._archive_path

  @property
  def make_javascript_deterministic(self):
    return self._make_javascript_deterministic

  @property
  def inject_scripts(self):
    return self._inject_scripts

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
