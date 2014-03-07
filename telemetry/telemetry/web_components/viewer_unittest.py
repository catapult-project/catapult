# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import StringIO

from telemetry.web_components import viewer

class SimpleViewer(viewer.Viewer):
  def __init__(self):
    super(SimpleViewer, self).__init__(
      tvcm_module_name='telemetry.web_components.viewer_unittest_data',
      js_class_name='telemetry.web_components.SimpleViewer',
      data_binding_property='dataToView')

  def WriteDataToFileAsJson(self, f):
    f.write("1\n")

class ViewerTests(unittest.TestCase):
  def testForSmoke(self):
    v = SimpleViewer()

    f = StringIO.StringIO()
    v.WriteViewerToFile(f)

  def testRead(self):
    v = SimpleViewer()

    f = StringIO.StringIO()
    v.WriteViewerToFile(f)

    f.seek(0)

    data = SimpleViewer.ReadDataObjectFromViewerFile(f)
    self.assertEquals(data, 1)
