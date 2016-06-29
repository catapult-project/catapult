# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.browser import browser_finder
from telemetry.testing import options_for_unittests


class SeriallyBrowserTestCase(unittest.TestCase):
  def __init__(self, methodName):
    super(SeriallyBrowserTestCase, self).__init__(methodName)
    self._private_methodname = methodName

  def shortName(self):
    """Returns the method name this test runs, without the package prefix."""
    return self._private_methodname

  @classmethod
  def Name(cls):
    return cls.__name__

  @classmethod
  def AddCommandlineArgs(cls, parser):
    pass

  @classmethod
  def setUpClass(cls):
    cls._finder_options = options_for_unittests.GetCopy()
    cls._platform = None
    cls._browser = None
    cls.platform = None
    cls.browser = None

  @classmethod
  def StartBrowser(cls, options):
    assert not cls.browser, 'Browser is started. Must close it first'
    browser_to_create = browser_finder.FindBrowser(options)
    cls.browser = browser_to_create.Create(options)
    cls._browser = cls.browser
    if not cls.platform:
      cls.platform = cls.browser.platform
      cls._platform = cls.platform
    else:
      assert cls.platform == cls.browser.platform, (
          'All browser launches within same test suite must use browsers on '
          'the same platform')

  @classmethod
  def StopBrowser(cls):
    assert cls.browser, 'Browser is not started'
    cls.browser.Close()
    cls.browser = None
    cls._browser = None

  @classmethod
  def tearDownClass(cls):
    if cls.platform:
      cls.platform.StopAllLocalServers()
    if cls.browser:
      cls.StopBrowser()

  @classmethod
  def SetStaticServerDir(cls, dir_path):
    assert cls.platform
    cls.platform.SetHTTPServerDirectories(dir_path)

  @classmethod
  def UrlOfStaticFilePath(cls, file_path):
    return cls.platform.http_server.UrlOf(file_path)
