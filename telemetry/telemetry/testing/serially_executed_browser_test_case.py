# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from py_utils import cloud_storage
from telemetry.internal.browser import browser_finder
from telemetry.testing import options_for_unittests
from telemetry.util import wpr_modes


class SeriallyExecutedBrowserTestCase(unittest.TestCase):
  def __init__(self, methodName):
    super(SeriallyExecutedBrowserTestCase, self).__init__(methodName)
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
    cls.platform = None
    cls.browser = None
    cls._browser_to_create = None
    cls._browser_options = None

  @classmethod
  def SetBrowserOptions(cls, browser_options):
    """Sets the browser option for the browser to create.

    Args:
      browser_options: Browser options object for the browser we want to test.
    """
    cls._browser_options = browser_options
    cls._browser_to_create = browser_finder.FindBrowser(browser_options)
    if not cls.platform:
      cls.platform = cls._browser_to_create.platform
      cls.platform.network_controller.InitializeIfNeeded()
    else:
      assert cls.platform == cls._browser_to_create.platform, (
          'All browser launches within same test suite must use browsers on '
          'the same platform')

  @classmethod
  def StartWPRServer(cls, archive_path=None, archive_bucket=None):
    """Start a webpage replay server.

    Args:
      archive_path: Path to the WPR file. If there is a corresponding sha1 file,
          this archive will be automatically downloaded from Google Storage.
      archive_bucket: The bucket to look for the WPR archive.
    """
    assert cls._browser_options, (
        'Browser options must be set with |SetBrowserOptions| prior to '
        'starting WPR')
    assert not cls.browser, 'WPR must be started prior to browser being started'

    cloud_storage.GetIfChanged(archive_path, archive_bucket)
    cls.platform.network_controller.Open(wpr_modes.WPR_REPLAY, [])
    cls.platform.network_controller.StartReplay(archive_path=archive_path)

  @classmethod
  def StopWPRServer(cls):
    cls.platform.network_controller.StopReplay()

  @classmethod
  def StartBrowser(cls):
    assert cls._browser_options, (
        'Browser options must be set with |SetBrowserOptions| prior to '
        'starting WPR')
    assert not cls.browser, 'Browser is started. Must close it first'

    cls.browser = cls._browser_to_create.Create(cls._browser_options)

  @classmethod
  def StopBrowser(cls):
    assert cls.browser, 'Browser is not started'
    cls.browser.Close()
    cls.browser = None

  @classmethod
  def tearDownClass(cls):
    if cls.platform:
      cls.platform.StopAllLocalServers()
      cls.platform.network_controller.Close()
    if cls.browser:
      cls.StopBrowser()

  @classmethod
  def SetStaticServerDirs(cls, dirs_path):
    assert cls.platform
    assert isinstance(dirs_path, list)
    cls.platform.SetHTTPServerDirectories(dirs_path)

  @classmethod
  def UrlOfStaticFilePath(cls, file_path):
    return cls.platform.http_server.UrlOf(file_path)
