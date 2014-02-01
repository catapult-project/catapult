# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from build import tvcm_stub
import tvcm

toplevel_path = os.path.abspath(os.path.join('..'),
                                os.path.dirname(__file__))
tvcm_path = os.path.join(toplevel_path, 'third_party', 'tvcm')
src_path = os.path.join(toplevel_path, 'src')
third_party_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../third_party"))


def _try_to_import_telemetry():
  trace_viewer_path = os.path.join(os.path.dirname(__file__), '..')
  parent_chrome_path = os.path.join(trace_viewer_path, '..', '..')
  telemetry_path = os.path.abspath(
      os.path.join(parent_chrome_path, 'tools', 'telemetry'))
  if not os.path.exists(os.path.join(telemetry_path, 'telemetry', '__init__.py')):
    return False
  if not telemetry_path in sys.path:
    sys.path.append(telemetry_path)
  return True


if _try_to_import_telemetry:
  import telemetry
  from telemetry.core import browser_finder
  from telemetry.core import browser_options
  from telemetry.core import local_server
else:
  telemetry = None


class TVCMModulesTest(unittest.TestCase):
  def __init__(self, source_paths, raw_data_paths):
    super(TVCMModuleTest, self).__init__(methodName='runTest')
    self._source_paths = source_paths
    self._raw_data_paths = raw_data_paths

  def setUp(self):
    if telemetry == None:
      raise Exception('Telemetry not found. Cannot run src/ tests')
    self._browser = None
    self._tab = None

    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('telemetry_perf_test.py')
    options, _ = parser.parse_args(['--browser', 'any'])
    browser_to_create = browser_finder.FindBrowser(options)
    assert browser_to_create
    self._browser = browser_to_create.Create()
    self._tab = b.tabs[0]

  def runTest(self):


    # Bring up devserver and navigate to tests.html
    pass

  def tearDow(self):
    self._tabs = None
    if self._browser:f
      self._browser.Close()

class LocalDevServer(local_server.LocalServer):
  def __init__(self, browser_backend, source_paths, raw_data_paths):
    args = {'source_paths': source_paths,
            'raw_data_paths': raw_data_paths}
    super(LocalDevServer, self).__init__(
      LocalDevServerBackend, browser_backend, args)


class LocalDevServerBackend(local_server.LocalServerBackend):
  def __init__(self):
    super(LocalServerBackend, self).__init__()
    self.server = None

  def StartAndGetNamedPortPairs(self, args):
    source_paths = args['source_paths']
    raw_data_paths = args['raw_data_paths']

    self.server = tvcm.DevServer(port=0)
    for path in self._source_paths:
      self.server.AddSourcePathMapping('/', path)
    for path in self._raw_data_paths:
      self.server.AddDataPathMapping('/', path)
    return [local_server.NamedPortPair('http', server.port)]

  def ServeForever(self):
    return self.server.serve_forever()


def load_tests(loader, tests, pattern):
  suite = unittest.TestSuite()
  suite.addTest(TVCMModuleTest([src_path, tvcm_path],
                               [third_party_path]))
  return suite
