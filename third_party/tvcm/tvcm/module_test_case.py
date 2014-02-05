# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from tvcm import dev_server

def _try_to_import_telemetry():
  trace_viewer_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
  parent_chrome_path = os.path.join(trace_viewer_path, '..', '..')
  telemetry_path = os.path.abspath(
      os.path.join(parent_chrome_path, 'tools', 'telemetry'))
  if not os.path.exists(os.path.join(telemetry_path, 'telemetry', '__init__.py')):
    return False
  if not telemetry_path in sys.path:
    sys.path.append(telemetry_path)
  return True


if _try_to_import_telemetry():
  import telemetry
  from telemetry.core import browser_finder
  from telemetry.core import browser_options
  from telemetry.core import local_server
else:
  telemetry = None


class Runner(object):
  def __init__(self, source_paths, raw_data_paths):
    self._source_paths = source_paths
    self._raw_data_paths = raw_data_paths

    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('telemetry_perf_test.py')
    options, _ = parser.parse_args(['--browser', 'any'])
    browser_to_create = browser_finder.FindBrowser(options)

    if telemetry == None:
      raise Exception('Telemetry not found. Cannot run src/ tests')
    self._browser = None
    self._tab = None

    assert browser_to_create
    self._browser = browser_to_create.Create()
    self._browser.Start()
    self._tab = self._browser.tabs[0]

    self._server = _LocalDevServer(self._source_paths, self._raw_data_paths)
    self._browser.StartLocalServer(self._server)

  def NavigateToPath(self, path):
    self._tab.Navigate(self._server.url + path)
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def EvaluateJavaScript(self, js, timeout=120):
    self._tab.EvaluateJavaScript(js, timeout)

  def WaitForJavaScriptExpression(self, js, timeout=120):
    self._tab.WaitForJavaScriptExpression(js, timeout)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  def Close(self):
    if self._server:
      self._server.Close()
      self._server = None

    if self._tab:
      self._tab = None

    if self._browser:
      self._browser.Close()
      self._browser = None


class ModuleTestCase(unittest.TestCase):
  def __init__(self, source_paths, raw_data_paths, method_name):
    super(ModuleTestCase, self).__init__(methodName=method_name)
    self.source_paths = source_paths
    self.raw_data_paths = raw_data_paths

  def runTest(self):
    with Runner(self.source_paths, self.raw_data_paths) as runner:
      runner.NavigateToPath('/base/tests.html')
      runner.EvaluateJavaScript("""
    if (base === undefined || base.unittest === undefined) {
      window.__testsDone = true;
      window.__testsPass = false;
    } else {
      window.__testsDone = false;
      window.__testsPass = false;
      base.unittest.whenDone.then(
        function resolve() {
          window.__testsDone = true;
          window.__testsPass = true;
        },
        function reject() {
          window.__testsDone = true;
          window.__testsPass = false;
        });
    }
    """)
      runner.WaitForJavaScriptExpression("window.__testsDone",
                                         timeout=120)
      self.assertTrue(runner.EvaluateJavaScript("window.__testsPass"))


class _LocalDevServer(local_server.LocalServer):
  def __init__(self, source_paths, raw_data_paths):
    super(_LocalDevServer, self).__init__(_LocalDevServerBackend)
    self.source_paths = source_paths
    self.raw_data_paths = raw_data_paths

  def GetBackendStartupArgs(self):
    return {'source_paths': self.source_paths,
            'raw_data_paths': self.raw_data_paths}

  @property
  def url(self):
    return self.forwarders['http'].url


class _LocalDevServerBackend(local_server.LocalServerBackend):
  def __init__(self):
    super(_LocalDevServerBackend, self).__init__()
    self.server = None

  def StartAndGetNamedPortPairs(self, args):
    self.server = dev_server.DevServer(port=0, quiet=True)
    for path in args['source_paths']:
      self.server.AddSourcePathMapping(path)
    for path in args['raw_data_paths']:
      self.server.AddDataPathMapping(path)
    return [local_server.NamedPortPair('http', self.server.port)]

  def ServeForever(self):
    return self.server.serve_forever()
