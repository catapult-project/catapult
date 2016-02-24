# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import time

from profile_chrome import controllers
from profile_chrome import util

_DDMS_SAMPLING_FREQUENCY_US = 100


class DdmsController(controllers.BaseController):
  def __init__(self, device, package_info):
    controllers.BaseController.__init__(self)
    self._device = device
    self._package = package_info.package
    self._output_file = None
    self._supports_sampling = self._SupportsSampling()

  def __repr__(self):
    return 'ddms profile'

  def _SupportsSampling(self):
    for line in self._device.RunShellCommand('am --help'):
      if re.match(r'.*am profile start.*--sampling', line):
        return True
    return False

  def StartTracing(self, _):
    self._output_file = (
        '/data/local/tmp/ddms-profile-%s' % util.GetTraceTimestamp())
    cmd = 'am profile start '
    if self._supports_sampling:
      cmd += '--sampling %d ' % _DDMS_SAMPLING_FREQUENCY_US
    cmd += '%s %s' % (self._package, self._output_file)
    self._device.RunShellCommand(cmd)

  def StopTracing(self):
    self._device.RunShellCommand('am profile stop %s' % self._package)

  def PullTrace(self):
    if not self._output_file:
      return None

    # Wait for the trace file to get written.
    time.sleep(1)

    host_file = os.path.join(
        os.path.curdir, os.path.basename(self._output_file))
    self._device.PullFile(self._output_file, host_file)
    return host_file
