# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import posixpath
import uuid
import sys
import tempfile
import time

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry import decorators
from telemetry.core import exceptions
from telemetry.internal.backends import app_backend
from telemetry.internal.browser import web_contents
from telemetry.internal.results import artifact_logger
from telemetry.util import screenshot


class ExtensionsNotSupportedException(Exception):
  pass


class BrowserBackend(app_backend.AppBackend):
  """A base class for browser backends."""

  def __init__(self, platform_backend, browser_options,
               supports_extensions, tab_list_backend):
    assert browser_options.browser_type
    super(BrowserBackend, self).__init__(browser_options.browser_type,
                                         platform_backend)
    self.browser_options = browser_options
    self._supports_extensions = supports_extensions
    self._tab_list_backend_class = tab_list_backend
    self._dump_finder = None
    self._tmp_minidump_dir = tempfile.mkdtemp()
    self._symbolized_minidump_paths = set([])

  def SetBrowser(self, browser):
    super(BrowserBackend, self).SetApp(app=browser)

  @property
  def log_file_path(self):
    # Specific browser backend is responsible for overriding this properly.
    raise NotImplementedError

  def GetLogFileContents(self):
    if not self.log_file_path:
      return 'No log file'
    with file(self.log_file_path) as f:
      return f.read()

  def UploadLogsToCloudStorage(self):
    """ Uploading log files produce by this browser instance to cloud storage.

    Check supports_uploading_logs before calling this method.
    """
    assert self.supports_uploading_logs
    remote_path = (self.browser_options.logs_cloud_remote_path or
                   'log_%s' % uuid.uuid4())
    cloud_url = cloud_storage.Insert(
        bucket=self.browser_options.logs_cloud_bucket,
        remote_path=remote_path,
        local_path=self.log_file_path)
    sys.stderr.write('Uploading browser log to %s\n' % cloud_url)

  @property
  def browser(self):
    return self.app

  @property
  def browser_type(self):
    return self.app_type

  @property
  def supports_uploading_logs(self):
    # Specific browser backend is responsible for overriding this properly.
    return False

  @property
  def supports_extensions(self):
    """True if this browser backend supports extensions."""
    return self._supports_extensions

  @property
  def supports_tab_control(self):
    raise NotImplementedError()

  @property
  @decorators.Cache
  def tab_list_backend(self):
    return self._tab_list_backend_class(self)

  @property
  def supports_app_ui_interactions(self):
    return False

  def Start(self, startup_args):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()

  def IsAppRunning(self):
    return self.IsBrowserRunning()

  def GetStandardOutput(self):
    raise NotImplementedError()

  def PullMinidumps(self):
    """Pulls any minidumps off a test device if necessary."""
    pass

  def CollectDebugData(self, log_level):
    """Attempts to symbolize all currently unsymbolized minidumps and log them.

    Additionally, attempts to capture a screenshot and save it as an artifact.

    Platforms may override this to provide other crash information in addition
    to the symbolized minidumps.

    Args:
      log_level: The logging level to use from the logging module, e.g.
          logging.ERROR.
    """
    self._CollectScreenshot(log_level)
    self._SymbolizeAndLogMinidumps(log_level)

  def _CollectScreenshot(self, log_level):
    """Helper function to handle the screenshot portion of CollectDebugData.

    Attempts to take a screenshot at the OS level and save it as an artifact.

    Args:
      log_level: The logging level to use from the logging module, e.g.
          logging.ERROR.
    """
    screenshot_handle = screenshot.TryCaptureScreenShot(self.browser.platform)
    if screenshot_handle:
      with open(screenshot_handle.GetAbsPath(), 'rb') as infile:
        now = datetime.datetime.now()
        suffix = now.strftime('%Y-%m-%d-%H-%M-%S')
        artifact_name = posixpath.join(
            'debug_screenshots', 'screenshot-' + suffix)
        logging.log(
            log_level, 'Saving screenshot as artifact %s', artifact_name)
        artifact_logger.CreateArtifact(artifact_name, infile.read())
    else:
      logging.log(log_level, 'Failed to capture screenshot')

  def _SymbolizeAndLogMinidumps(self, log_level):
    """Helper function to handle the minidump portion of CollectDebugData.

    Attempts to find all unsymbolized minidumps, symbolize them, save the
    results as artifacts, and log the results.

    Args:
      log_level: The logging level to use from the logging module, e.g.
          logging.ERROR.
    """
    paths = self.GetAllUnsymbolizedMinidumpPaths()
    if not paths:
      logging.log(log_level, 'No unsymbolized minidump paths')
      return
    logging.log(log_level, 'Unsymbolized minidump paths: ' + str(paths))
    for unsymbolized_path in paths:
      valid, output = self.SymbolizeMinidump(unsymbolized_path)
      # Store the symbolization attempt as an artifact.
      minidump_name = os.path.basename(unsymbolized_path)
      artifact_name = posixpath.join('symbolize_attempts', minidump_name)
      logging.log(log_level, 'Saving symbolization attempt as artifact %s',
                  artifact_name)
      artifact_logger.CreateArtifact(artifact_name, output)
      if valid:
        logging.log(log_level, 'Symbolized minidump:\n%s', output)
      else:
        logging.log(
            log_level,
            'Minidump symbolization failed, check artifact %s for output',
            artifact_name)

  def GetStackTrace(self):
    """Gets a stack trace if a valid minidump is found.

    Returns:
      A tuple (valid, output). |valid| is True if a valid minidump was found or
      False otherwise. |output| contains an error message if |valid| is False,
      otherwise it contains the output of the minidump symbolization process.
    """
    raise NotImplementedError()

  def GetMostRecentMinidumpPath(self):
    """Gets the most recent minidump that has been written to disk.

    Returns:
      The path to the most recent minidump on disk, or None if no minidumps are
      found.
    """
    self.PullMinidumps()
    dump_path, explanation = self._dump_finder.GetMostRecentMinidump(
        self._tmp_minidump_dir)
    logging.info('\n'.join(explanation))
    return dump_path

  def GetRecentMinidumpPathWithTimeout(self, timeout_s, oldest_ts):
    """Get a path to a recent minidump, blocking until one is available.

    Similar to GetMostRecentMinidumpPath, but does not assume that any pending
    dumps have been written to disk yet. Instead, waits until a suitably fresh
    minidump is found or the timeout is reached.

    Args:
      timeout_s: The timeout in seconds.
      oldest_ts: The oldest allowable timestamp (in seconds since epoch) that a
          minidump was created at for it to be considered fresh enough to
          return. Defaults to a minute from the current time if not set.

    Returns:
      None if the timeout is hit or a str containing the path to the found
      minidump if a suitable one is found.
    """
    assert timeout_s > 0
    assert oldest_ts >= 0
    explanation = ['No explanation returned.']
    start_time = time.time()
    try:
      while time.time() - start_time < timeout_s:
        self.PullMinidumps()
        dump_path, explanation = self._dump_finder.GetMostRecentMinidump(
            self._tmp_minidump_dir)
        if not dump_path or os.path.getmtime(dump_path) < oldest_ts:
          continue
        return dump_path
      return None
    finally:
      logging.info('\n'.join(explanation))

  def GetAllMinidumpPaths(self):
    """Get all paths to minidumps currently written to disk.

    Returns:
      A list of paths to all found minidumps.
    """
    self.PullMinidumps()
    paths, explanation = self._dump_finder.GetAllMinidumpPaths(
        self._tmp_minidump_dir)
    logging.info('\n'.join(explanation))
    return paths

  def GetAllUnsymbolizedMinidumpPaths(self):
    """Get all paths to minidumps have have not yet been symbolized.

    Returns:
      A list of paths to all found minidumps that have not been symbolized yet.
    """
    minidump_paths = set(self.GetAllMinidumpPaths())
    # If we have already symbolized paths remove them from the list
    unsymbolized_paths = (
        minidump_paths - self._symbolized_minidump_paths)
    return list(unsymbolized_paths)

  def SymbolizeMinidump(self, minidump_path):
    """Symbolizes the given minidump.

    Args:
      minidump_path: The path to the minidump to symbolize.

    Returns:
      A tuple (valid, output). |valid| is True if the minidump was symbolized,
      otherwise False. |output| contains an error message if |valid| is False,
      otherwise it contains the symbolized minidump.
    """
    raise NotImplementedError()

  def GetSystemInfo(self):
    return None

  @property
  def supports_memory_dumping(self):
    return False

  def DumpMemory(self, timeout=None):
    raise NotImplementedError()

# pylint: disable=invalid-name
  @property
  def supports_overriding_memory_pressure_notifications(self):
    return False

  def SetMemoryPressureNotificationsSuppressed(
      self, suppressed, timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    raise NotImplementedError()

  def SimulateMemoryPressureNotification(
      self, pressure_level, timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    raise NotImplementedError()

  @property
  def supports_cpu_metrics(self):
    raise NotImplementedError()

  @property
  def supports_memory_metrics(self):
    raise NotImplementedError()

  @property
  def supports_overview_mode(self): # pylint: disable=invalid-name
    return False

  def EnterOverviewMode(self, timeout): # pylint: disable=unused-argument
    raise exceptions.StoryActionError('Overview mode is not supported')

  def ExitOverviewMode(self, timeout): # pylint: disable=unused-argument
    raise exceptions.StoryActionError('Overview mode is not supported')
