# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from tvcm import dev_server
from tvcm import project as project_module
from tvcm import test_runner

def _TryToImportTelemetry():
  # Maybe telemetry is just hanging around in PYTHONPATH
  try:
    import telemetry
    return True
  except:
    pass

  # Try to find it in a likely location.
  trace_viewer_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
  parent_chrome_path = os.path.join(trace_viewer_path, '..', '..')
  telemetry_path = os.path.abspath(
      os.path.join(parent_chrome_path, 'tools', 'telemetry'))
  if not os.path.exists(os.path.join(telemetry_path, 'telemetry', '__init__.py')):
    return False
  if not telemetry_path in sys.path:
    sys.path.append(telemetry_path)
  return True


if _TryToImportTelemetry():
  import telemetry
  from telemetry.core import browser_finder
  from telemetry.core import browser_options
  from telemetry.core import local_server
  from telemetry.unittest import options_for_unittests as \
      telemetry_options_for_unittests

  class _LocalDevServer(local_server.LocalServer):
    def __init__(self, project):
      super(_LocalDevServer, self).__init__(_LocalDevServerBackend)
      self.project = project

    def GetBackendStartupArgs(self):
      return self.project.AsDict()

    @property
    def url(self):
      return self.forwarder.url


  class _LocalDevServerBackend(local_server.LocalServerBackend):
    def __init__(self):
      super(_LocalDevServerBackend, self).__init__()
      self.server = None

    def StartAndGetNamedPorts(self, args):
      self.server = dev_server.DevServer(port=0, quiet=True,
                                         project=project_module.Project.FromDict(args))
      return [local_server.NamedPort('http', self.server.port)]

    def ServeForever(self):
      return self.server.serve_forever()

else:
  telemetry = None


def IsSupported():
  return telemetry != None

def GetAvailableBrowserTypes():
  if telemetry == None:
    sys.stderr.write(
      'Could not find telemetry in $PYTHONPATH. No browsers will run\n')
    return ''
  from telemetry.core import browser_finder
  finder_options = browser_options.BrowserFinderOptions()
  return ','.join(browser_finder.GetAllAvailableBrowserTypes(finder_options) +
                  ['any'])

class BrowserController(object):
  def __init__(self, project):
    self._project = project
    self._browser = None
    self._tab = None
    self._server = None

    if telemetry == None:
      raise Exception('Not supported: trace-viewer must be inside a chrome checkout for this to work.')

    # If run in the context of the telemetry test runner, use
    # telemetry's browser options instead.
    if telemetry_options_for_unittests.AreSet():
      finder_options = telemetry_options_for_unittests.GetCopy()
    else:
      finder_options = browser_options.BrowserFinderOptions()
      parser = finder_options.CreateParser('telemetry_perf_test.py')
      from tvcm import test_runner
      finder_options, _ = parser.parse_args(
        ['--browser', test_runner.BROWSER_TYPE_TO_USE])


    finder_options.browser_options.warn_if_no_flash = False
    browser_to_create = browser_finder.FindBrowser(finder_options)
    if not browser_to_create:
      raise Exception(
          'Failed to find the specified browser. ' +
          ' Its binary is probably broken.')

    self._browser = browser_to_create.Create()
    self._tab = None

    try:
      self._browser.Start()
      self._tab = self._browser.tabs[0]

      self._server = _LocalDevServer(self._project)
      self._browser.StartLocalServer(self._server)

    except:
      self._browser.Close()
      raise

  def NavigateToPath(self, path):
    self._tab.Navigate(self._server.url + path)
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def EvaluateJavaScript(self, js, timeout=120):
    return self._tab.EvaluateJavaScript(js, timeout)

  def WaitForJavaScriptExpression(self, js, timeout=120):
    self._tab.WaitForJavaScriptExpression(js, timeout)

  def EvaluateThennableAndWait(self, js, timeout=120):
    if js.endswith(';'):
      raise Exception('Must not end with ;');

    full_js = """
    window.__thennableSucceeded = undefined;
    window.__thennableResult = undefined;
    (function() {
      var thennable;
      try {
        thennable = %s;
      } catch(e) {
        window.__thennableSucceeded = false;
        window.__thennableResult = e.stack ? e.stack : e;
        return;
      }
      thennable.then(
          function(res) {
            window.__thennableSucceeded = true;
            window.__thennableResult = res;
          },
          function(err) {
            window.__thennableSucceeded = false;
            if (typeof(err) === 'string') {
              window.__thennableResult = err;
              return;
            }
            if (err.stack)
               window.__thennableResult = err.stack;
            else
               window.__thennableResult = err;
          });
    })();
""" % js
    self._tab.ExecuteJavaScript(full_js)
    self._tab.WaitForJavaScriptExpression('window.__thennableSucceeded !== undefined',
                                          timeout=timeout)
    val = self._tab.EvaluateJavaScript('window.__thennableSucceeded')
    if val == False:
      raise Exception(str(self._tab.EvaluateJavaScript(
          'window.__thennableResult')))
    return self._tab.EvaluateJavaScript('window.__thennableResult')

  @property
  def stdout_enabled(self):
    return self._tab.message_output_stream != None

  @stdout_enabled.setter
  def stdout_enabled(self, enabled):
    if enabled:
      self._tab.message_output_stream = sys.stderr
    else:
      self._tab.message_output_stream = None

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
