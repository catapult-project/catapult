# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import StringIO

from telemetry.web_components import web_component

class SimpleWebComponent(web_component.WebComponent):
  def __init__(self):
    super(SimpleWebComponent, self).__init__(
      tvcm_module_name='telemetry.web_components.viewer_unittest_data',
      js_class_name='telemetry.web_components.SimpleWebComponent',
      data_binding_property='dataToView')

  def WriteDataToFileAsJson(self, f):
    f.write("1\n")

class WebComponentTests(unittest.TestCase):
  def testForSmoke(self):
    v = SimpleWebComponent()

    f = StringIO.StringIO()
    v.WriteWebComponentToFile(f)

  def testRead(self):
    v = SimpleWebComponent()

    f = StringIO.StringIO()
    v.WriteWebComponentToFile(f)

    f.seek(0)

    data = SimpleWebComponent.ReadDataObjectFromWebComponentFile(f)
    self.assertEquals(data, 1)
