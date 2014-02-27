# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


from telemetry.core import util
from tvcm import project as project_module


class WebComponentsProject(project_module.Project):
  telemetry_path = os.path.abspath(util.GetTelemetryDir())

  trace_viewer_path = os.path.abspath(os.path.join(
      util.GetChromiumSrcDir(),
      'third_party', 'trace-viewer'))

  def __init__(self):
    super(WebComponentsProject, self).__init__(
      [self.telemetry_path])
