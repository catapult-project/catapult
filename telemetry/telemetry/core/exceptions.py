# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys


class Error(Exception):
  """Base class for Telemetry exceptions."""
  def __init__(self, msg=''):
    super(Error, self).__init__(msg)
    self._debugging_messages = []

  def AddDebuggingMessage(self, msg):
    """Adds a message to the description of the exception.

    Many Telemetry exceptions arise from failures in another application. These
    failures are difficult to pinpoint. This method allows Telemetry classes to
    append useful debugging information to the exception. This method also logs
    information about the location from where it was called.
    """
    frame = sys._getframe(1)
    line_number = frame.f_lineno
    file_name = frame.f_code.co_filename
    function_name = frame.f_code.co_name
    call_site = '%s:%s %s' % (file_name, line_number, function_name)
    annotated_message = '(%s) %s' % (call_site, msg)

    self._debugging_messages.append(annotated_message)

  def __str__(self):
    divider = '\n' + '*' * 80 + '\n'
    output = super(Error, self).__str__()
    for message in self._debugging_messages:
      output += divider
      output += message
    return output


class PlatformError(Error):
  """ Represents an exception thrown when constructing platform. """


class TimeoutException(Error):
  """The operation failed to complete because of a timeout.

  It is possible that waiting for a longer period of time would result in a
  successful operation.
  """
  pass


class AppCrashException(Error):
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


class ProcessGoneException(Error):
  """Represents a process that no longer exists for an unknown reason."""


class IntentionalException(Error):
  """Represent an exception raised by a unittest which is not printed."""


class LoginException(Error):
  pass


class EvaluateException(Error):
  pass


class ProfilingException(Error):
  pass


class PathMissingError(Error):
  """ Represents an exception thrown when an expected path doesn't exist. """


class UnknownPackageError(Error):
  """ Represents an exception when encountering an unsupported Android APK. """


class PackageDetectionError(Error):
  """ Represents an error when parsing an Android APK's package. """

class AndroidDeviceParsingError(Error):
  """Represents an error when parsing output from an android device"""
