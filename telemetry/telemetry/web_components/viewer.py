# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import string

from telemetry.web_components import web_components_project
from tvcm import generate


class Viewer(object):
  """An HTML-based viewer of data, built out of telemetry components.

  A viewer is used to visualize complex data that is produced from a telemtry
  benchmark. A viewer is backed by a .js file that contains a telemetry
  component. Python-side, it knows enough to instantiate that component and pass
  it its data. Viewers are typically written to HTML files in order to be
  displayed.

  Python-side, a viewer class can be anything, as long as it implements the
  WriteDataToFileAsJSON. The data written here is passed to the
  data_binding_property of the JS-side class specified during the viewer's
  construction.

  """
  def __init__(self, tvcm_module_name, js_class_name, data_binding_property):
    self._tvcm_module_name = tvcm_module_name
    self._js_class_name = js_class_name
    self._data_binding_property = data_binding_property

  def WriteDataToFileAsJson(self, f):
    raise NotImplementedError()

  def WriteViewerToFile(self, f):
    project = web_components_project.WebComponentsProject()
    load_sequence = project.CalcLoadSequenceForModuleNames(
      [self._tvcm_module_name])

    with open(os.path.join(os.path.dirname(__file__),
                           'viewer_bootstrap.js')) as bfile:
      bootstrap_js_template = string.Template(bfile.read())
    bootstrap_js = bootstrap_js_template.substitute(
      js_class_name=self._js_class_name,
      data_binding_property=self._data_binding_property)

    bootstrap_script = generate.ExtraScript(text_content=bootstrap_js)

    class ViewerDataScript(generate.ExtraScript):
      def __init__(self, results_component):
        super(ViewerDataScript, self).__init__()
        self._results_component = results_component

      def WriteToFile(self, output_file):
        output_file.write('<script id="viewer-data" type="application/json">\n')
        self._results_component.WriteDataToFileAsJson(output_file)
        output_file.write('</script>\n')


    generate.GenerateStandaloneHTMLToFile(
        f, load_sequence,
        title='Telemetry results',
        extra_scripts=[bootstrap_script, ViewerDataScript(self)])
