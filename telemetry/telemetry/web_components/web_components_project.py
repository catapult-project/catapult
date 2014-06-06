# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


from telemetry.core import util
from trace_viewer import trace_viewer_project


class WebComponentsProject(trace_viewer_project.TraceViewerProject):
  telemetry_path = os.path.abspath(util.GetTelemetryDir())

  d3_path = os.path.abspath(os.path.join(
      telemetry_path,
      'third_party', 'd3'))

  def __init__(self):
    super(WebComponentsProject, self).__init__(
      [self.telemetry_path, self.d3_path])
