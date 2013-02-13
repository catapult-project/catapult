# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import shutil
import tempfile
import unittest

from telemetry import browser_finder
from telemetry import extension_to_load
from telemetry import options_for_unittests

class ExtensionTest(unittest.TestCase):
  def testExtension(self):
    extension_path = os.path.join(os.path.dirname(__file__),
        '..', 'unittest_data', 'simple_extension')
    load_extension = extension_to_load.ExtensionToLoad(extension_path)

    options = options_for_unittests.GetCopy()
    options.extensions_to_load = [load_extension]
    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      # Could not find a browser that supports extensions.
      return

    with browser_to_create.Create() as b:
      extension = b.extensions[load_extension]
      assert extension
      extension.ExecuteJavaScript("setTestVar('abcdef')")
      self.assertEquals('abcdef', extension.EvaluateJavaScript("_testVar"))

class MultipleExtensionTest(unittest.TestCase):
  def setUp(self):
    """ Copy the manifest and background.js files of simple_extension to a
    number of temporary directories to load as extensions"""
    self._extension_dirs = [tempfile.mkdtemp()
                            for i in range(3)] # pylint: disable=W0612
    src_extension_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
        '..', 'unittest_data', 'simple_extension'))
    manifest_path = os.path.join(src_extension_dir, 'manifest.json')
    script_path = os.path.join(src_extension_dir, 'background.js')
    for d in self._extension_dirs:
      shutil.copy(manifest_path, d)
      shutil.copy(script_path, d)
    self._extensions_to_load = [extension_to_load.ExtensionToLoad(d)
                                for d in self._extension_dirs]
    options = options_for_unittests.GetCopy()
    options.extensions_to_load = self._extensions_to_load
    browser_to_create = browser_finder.FindBrowser(options)
    self._browser = None
    # May not find a browser that supports extensions.
    if browser_to_create:
      self._browser = browser_to_create.Create()

  def tearDown(self):
    if self._browser:
      self._browser.Close()
    for d in self._extension_dirs:
      shutil.rmtree(d)

  def testMultipleExtensions(self):
    if not self._browser:
      return

    # Test contains.
    loaded_extensions = filter(lambda e: e in self._browser.extensions,
                               self._extensions_to_load)
    self.assertEqual(len(loaded_extensions), len(self._extensions_to_load))

    for load_extension in self._extensions_to_load:
      extension = self._browser.extensions[load_extension]
      assert extension
      extension.ExecuteJavaScript("setTestVar('abcdef')")
      self.assertEquals('abcdef', extension.EvaluateJavaScript("_testVar"))
