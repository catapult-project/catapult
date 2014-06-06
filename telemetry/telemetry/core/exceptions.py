# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class NativeBrowserCrashException(Exception):
  def __init__(self, browser=None, msg=''):
    super(NativeBrowserCrashException, self).__init__(msg)
    self._browser = browser
    self._msg = msg

  def __str__(self):
    if not self._browser:
      return super(NativeBrowserCrashException, self).__str__()
    divider = '*' * 80
    return '%s\nStack Trace:\n%s\n\t%s\n%s' % (
        super(NativeBrowserCrashException, self).__str__(), divider,
        self._browser.GetStackTrace().replace('\n', '\n\t'), divider)


class TabCrashException(NativeBrowserCrashException):
  """Represents a crash of the current tab, but not the overall browser.

  In this state, the tab is gone, but the underlying browser is still alive."""
  def __init__(self, browser, msg='Tab crashed'):
    super(TabCrashException, self).__init__(browser, msg)


class BrowserGoneException(NativeBrowserCrashException):
  """Represents a crash of the entire browser.

  In this state, all bets are pretty much off."""
  def __init__(self, browser, msg='Browser crashed'):
    super(BrowserGoneException, self).__init__(browser, msg)


class BrowserConnectionGoneException(BrowserGoneException):
  """Represents a browser that still exists but cannot be reached."""
  def __init__(self, browser, msg='Browser exists but the connection is gone'):
    super(BrowserConnectionGoneException, self).__init__(browser, msg)


class ProcessGoneException(Exception):
  """Represents a process that no longer exists for an unknown reason."""


class IntentionalException(Exception):
  """Represent an exception raised by a unittest which is not printed."""


class LoginException(Exception):
  pass


class EvaluateException(Exception):
  pass


class ProfilingException(Exception):
  pass
