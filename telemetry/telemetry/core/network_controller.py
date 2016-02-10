# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators


class NetworkController(object):
  """Control network settings and servers to simulate the Web.

  Network changes include forwarding device ports to host platform ports.
  Web Page Replay is used to record and replay HTTP/HTTPS responses.
  """

  def __init__(self, network_controller_backend):
    self._network_controller_backend = network_controller_backend

  def Open(self, wpr_mode, netsim, extra_wpr_args):
    self._network_controller_backend.Open(wpr_mode, netsim, extra_wpr_args)

  def Close(self):
    self._network_controller_backend.Close()

  def StartReplay(self, archive_path, make_javascript_deterministic=False):
    self._network_controller_backend.StartReplay(
        archive_path, make_javascript_deterministic)

  def StopReplay(self):
    self._network_controller_backend.StopReplay()

  @decorators.Deprecated(2016, 2, 29, 'Clients should switch to new network '
                         'controller API. See https://goo.gl/UzzrQA .')
  def SetReplayArgs(self,
                    archive_path,
                    wpr_mode,
                    netsim,
                    extra_wpr_args,
                    make_javascript_deterministic=False):
    self._network_controller_backend.SetReplayArgs(
        archive_path, wpr_mode, netsim, extra_wpr_args,
        make_javascript_deterministic)

  @decorators.Deprecated(2016, 2, 29, 'Clients should switch to new network '
                         'controller API. See https://goo.gl/UzzrQA .')
  def UpdateReplayForExistingBrowser(self):
    self._network_controller_backend.UpdateReplay()
