# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import HTMLParser
import json
import os
import string

from telemetry.web_components import web_components_project
from tvcm import generate


class WebComponent(object):
  """An HTML-based viewer of data, built out of telemetry components.

  A WebComponent is used to visualize complex data that is produced from a
  telemtry benchmark. A WebComponent is a Javascript class that can be
  data-bound, plus python-side bindings that let us write HTML files that
  instantiate that class and bind it to specific data.

  The primary job of the python side of a WebComponent is to implement the
  WriteDataToFileAsJson. The data written here is passed to the
  data_binding_property of the JS-side class.

  The primary job of the javascript side of a WebComponent is visualization: it
  takes the data from python and renders a UI for displaying that data in some
  manner.

  """
  def __init__(self, tvcm_module_name, js_class_name, data_binding_property):
    self._tvcm_module_name = tvcm_module_name
    self._js_class_name = js_class_name
    self._data_binding_property = data_binding_property
    self._data_to_view = None

  @property
  def data_to_view(self):
    return self._data_to_view

  @data_to_view.setter
  def data_to_view(self, data_to_view):
    self._data_to_view = data_to_view

  def WriteDataToFileAsJson(self, f):
    raise NotImplementedError()

  def GetDependentModuleNames(self):
    return [self._tvcm_module_name]

  def WriteWebComponentToFile(self, f):
    project = web_components_project.WebComponentsProject()
    load_sequence = project.CalcLoadSequenceForModuleNames(
      self.GetDependentModuleNames())

    with open(os.path.join(os.path.dirname(__file__),
                           'web_component_bootstrap.js')) as bfile:
      bootstrap_js_template = string.Template(bfile.read())
    bootstrap_js = bootstrap_js_template.substitute(
      js_class_name=self._js_class_name,
      data_binding_property=self._data_binding_property)

    bootstrap_script = generate.ExtraScript(text_content=bootstrap_js)

    class WebComponentDataScript(generate.ExtraScript):
      def __init__(self, results_component):
        super(WebComponentDataScript, self).__init__()
        self._results_component = results_component

      def WriteToFile(self, output_file):
        output_file.write('<script id="telemetry-web-component-data" ' +
                          'type="application/json">\n')
        self._results_component.WriteDataToFileAsJson(output_file)
        output_file.write('</script>\n')


    generate.GenerateStandaloneHTMLToFile(
        f, load_sequence,
        title='Telemetry results',
        extra_scripts=[bootstrap_script, WebComponentDataScript(self)])

  @staticmethod
  def ReadDataObjectFromWebComponentFile(f):
    """Reads the data inside a file written with WriteWebComponentToFile

    Returns None if the data wasn't found, the JSON.parse'd object on success.
    Raises exception if the HTML file was corrupt.

    """
    class MyHTMLParser(HTMLParser.HTMLParser):
      def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self._got_data_tag = False
        self._in_data_tag = False
        self._data_records = []

      def handle_starttag(self, tag, attrs):
        if tag != 'script':
          return
        id_attr = dict(attrs).get('id', None)
        if id_attr == 'telemetry-web-component-data':
          assert not self._got_data_tag
          self._got_data_tag = True
          self._in_data_tag = True

      def handle_endtag(self, tag):
        self._in_data_tag = False

      def handle_data(self, data):
        if self._in_data_tag:
          self._data_records.append(data)

      @property
      def data(self):
        if not self._got_data_tag:
          raise Exception('Missing <script> with #telemetry-web-component-data')
        if self._in_data_tag:
          raise Exception('Missing </script> on #telemetry-web-component-data')
        return json.loads(''.join(self._data_records))

    parser = MyHTMLParser()
    for line in f:
      parser.feed(line)
    return parser.data
