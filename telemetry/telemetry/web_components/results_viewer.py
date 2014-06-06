# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import sys

from telemetry.web_components import web_component


class ResultsViewer(web_component.WebComponent):
  def __init__(self, data_to_view=None):
    super(ResultsViewer, self).__init__(
      tvcm_module_name='telemetry.web_components.results_viewer',
      js_class_name='telemetry.web_components.ResultsViewer',
      data_binding_property='dataToView')
    self.data_to_view = data_to_view

  def WriteDataToFileAsJson(self, f):
    json.dump(self.data_to_view, f)


if __name__ == '__main__':
  x = ResultsViewer({'hello': 'world', 'nice': ['to', 'see', 'you']})
  x.WriteWebComponentToFile(sys.stdout)
