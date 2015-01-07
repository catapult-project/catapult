# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class PlatformError(Exception):
  """ Represents an exception thrown when constructing platform. """


class AppCrashException(Exception):
  def __init__(self, app=None, msg=''):
    super(AppCrashException, self).__init__(msg)
    self._app = app
    self._msg = msg

  def __str__(self):
    if not self._app:
      return super(AppCrashException, self).__str__()
    divider = '*' * 80
    return '%s\nStack Trace:\n%s\n\t%s\n%s' % (
        super(AppCrashException, self).__str__(), divider,
        self._app.GetStackTrace().replace('\n', '\n\t'), divider)


class DevtoolsTargetCrashException(AppCrashException):
  """Represents a crash of the current devtools target but not the overall app.

  This can be a tab or a WebView. In this state, the tab/WebView is
  gone, but the underlying browser is still alive.
  """
  def __init__(self, app, msg='Devtools target crashed'):
    super(DevtoolsTargetCrashException, self).__init__(app, msg)


class BrowserGoneException(AppCrashException):
  """Represents a crash of the entire browser.

  In this state, all bets are pretty much off."""
  def __init__(self, app, msg='Browser crashed'):
    super(BrowserGoneException, self).__init__(app, msg)


class BrowserConnectionGoneException(BrowserGoneException):
  """Represents a browser that still exists but cannot be reached."""
  def __init__(self, app, msg='Browser exists but the connection is gone'):
    super(BrowserConnectionGoneException, self).__init__(app, msg)


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


class PathMissingError(Exception):
  """ Represents an exception thrown when an expected path doesn't exist. """


class UnknownPackageError(Exception):
  """ Represents an exception when encountering an unsupported Android APK. """


class PackageDetectionError(Exception):
  """ Represents an error when parsing an Android APK's package. """
