# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re
import urllib2

from telemetry.core.backends.webdriver import webdriver_browser_backend


class WebDriverIEBackend(webdriver_browser_backend.WebDriverBrowserBackend):
  # For unsupported functions. pylint: disable=W0223

  def __init__(self, platform_backend, driver_creator, browser_options):
    super(WebDriverIEBackend, self).__init__(
        driver_creator=driver_creator,
        supports_extensions=False,
        browser_options=browser_options)
    self._platform_backend = platform_backend

  def GetProcessName(self, cmd_line):
    if re.search('SCODEF:\d+ CREDAT:\d+', cmd_line, re.IGNORECASE):
      return 'Content'
    else:
      return 'Manager'

  @property
  def pid(self):
    for pi in self._platform_backend.GetSystemProcessInfo():
      if (pi['ParentProcessId'] == self.driver.iedriver.process.pid and
          pi['Name'].lower() == 'iexplore.exe'):
        return pi['ProcessId']
    return None

  def Close(self):
    try:
      super(WebDriverIEBackend, self).Close()
    except urllib2.URLError:
      # CTRL + C makes IEDriverServer exits while leaving IE still running.
      for pi in self._platform_backend.GetSystemProcessInfo():
        if (pi['ParentProcessId'] == self.driver.iedriver.process.pid):
          self._platform_backend.KillProcess(pi['ProcessId'], True)

  def IsBrowserRunning(self):
    return self.pid is not None
