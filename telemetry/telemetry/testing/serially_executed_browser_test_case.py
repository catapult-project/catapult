# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.browser import browser_finder
from telemetry.testing import options_for_unittests


class SeriallyBrowserTestCase(unittest.TestCase):
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

  @classmethod
  def StartBrowser(cls, options):
    assert not cls._browser, 'Browser is started. Must close it first'
    browser_to_create = browser_finder.FindBrowser(options)
    cls._browser = browser_to_create.Create(options)
    if not cls._platform:
      cls._platform = cls._browser.platform
    else:
      assert cls._platform == cls._browser.platform, (
          'All browser launches within same test suite must use browsers on '
          'the same platform')

  @classmethod
  def StopBrowser(cls):
    assert cls._browser, 'Browser is not started'
    cls._browser.Close()
    cls._browser = None

  @classmethod
  def tearDownClass(cls):
    if cls._platform:
      cls._platform.StopAllLocalServers()
    if cls._browser:
      cls.StopBrowser()

  @classmethod
  def SetStaticServerDir(cls, dir_path):
    assert cls._platform
    cls._platform.SetHTTPServerDirectories(dir_path)

  @classmethod
  def UrlOfStaticFilePath(cls, file_path):
    return cls._platform.http_server.UrlOf(file_path)
