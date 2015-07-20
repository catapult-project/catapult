# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class NetworkController(object):
  """Control network settings and servers to simulate the Web.

  Network changes include forwarding device ports to host platform ports.
  Web Page Replay is used to record and replay HTTP/HTTPS responses.
  """

  def __init__(self, network_controller_backend):
    self._network_controller_backend = network_controller_backend

  def SetReplayArgs(self, archive_path, wpr_mode, netsim, extra_wpr_args,
                    make_javascript_deterministic=False):
    """Save the arguments needed for replay."""
    self._network_controller_backend.SetReplayArgs(
        archive_path, wpr_mode, netsim, extra_wpr_args,
        make_javascript_deterministic)

  def UpdateReplayForExistingBrowser(self):
    """Restart replay if needed for an existing browser.

    TODO(slamm): Drop this method when the browser_backend dependencies are
    moved to the platform. https://crbug.com/423962
    """
    self._network_controller_backend.UpdateReplay()
