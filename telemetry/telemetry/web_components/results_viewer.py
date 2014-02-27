# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import sys

from telemetry.web_components import viewer


class ResultsViewer(viewer.Viewer):
  def __init__(self, data_to_view):
    super(ResultsViewer, self).__init__(
      tvcm_module_name='telemetry.web_components.results_viewer',
      js_class_name='telemetry.web_components.ResultsViewer',
      data_binding_property='dataToView')

    self._data_to_view = data_to_view

  @property
  def data_to_view(self):
    return self._data_to_view

  def WriteDataToFileAsJson(self, f):
    json.dump(self._data_to_view, f)


if __name__ == '__main__':
  x = ResultsViewer({'hello': 'world', 'nice': ['to', 'see', 'you']})
  x.WriteViewerToFile(sys.stdout)
