# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pipes
import sys

from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_errors  # pylint: disable=F0401


def _QuoteIfNeeded(arg):
  # Properly escape "key=valueA valueB" to "key='valueA valueB'"
  # Values without spaces, or that seem to be quoted are left untouched.
  # This is required so CommandLine.java can parse valueB correctly rather
  # than as a separate switch.
  params = arg.split('=', 1)
  if len(params) != 2:
    return arg
  key, values = params
  if ' ' not in values:
    return arg
  if values[0] in '"\'' and values[-1] == values[0]:
    return arg
  return '%s=%s' % (key, pipes.quote(values))


class SetUpCommandLineFlags(object):
  """A context manager for setting up the android command line flags.

  This provides a readable way of using the android command line backend class.
  Example usage:

      with android_command_line_backend.SetUpCommandLineFlags(
          adb, backend_settings, startup_args):
        # Something to run while the command line flags are set appropriately.
  """
  def __init__(self, adb, backend_settings, startup_args):
    self._android_command_line_backend = _AndroidCommandLineBackend(
        adb, backend_settings, startup_args)

  def __enter__(self):
    self._android_command_line_backend.SetUpCommandLineFlags()

  def __exit__(self, *args):
    self._android_command_line_backend.RestoreCommandLineFlags()


class _AndroidCommandLineBackend(object):
  """The backend for providing command line flags on android.

  There are command line flags that Chromium accept in order to enable
  particular features or modify otherwise default functionality. To set the
  flags for Chrome on Android, specific files on the device must be updated
  with the flags to enable. This class provides a wrapper around this
  functionality.
  """

  def __init__(self, adb, backend_settings, startup_args):
    self._adb = adb
    self._backend_settings = backend_settings
    self._startup_args = startup_args
    self._saved_command_line_file_contents = None

  @property
  def command_line_file(self):
    return self._backend_settings.GetCommandLineFile(self._adb.IsUserBuild())

  def SetUpCommandLineFlags(self):
    args = [self._backend_settings.pseudo_exec_name]
    args.extend(self._startup_args)
    content = ' '.join(_QuoteIfNeeded(arg) for arg in args)

    try:
      # Save the current command line to restore later, except if it appears to
      # be a  Telemetry created one. This is to prevent a common bug where
      # --host-resolver-rules borks people's browsers if something goes wrong
      # with Telemetry.
      self._saved_command_line_file_contents = self._ReadFile()
      if '--host-resolver-rules' in self._saved_command_line_file_contents:
        self._saved_command_line_file_contents = None
    except device_errors.CommandFailedError:
      self._saved_command_line_file_contents = None

    try:
      self._WriteFile(content)
    except device_errors.CommandFailedError as exc:
      logging.critical(exc)
      logging.critical('Cannot set Chrome command line. '
                       'Fix this by flashing to a userdebug build.')
      sys.exit(1)

  def RestoreCommandLineFlags(self):
    if self._saved_command_line_file_contents is None:
      self._RemoveFile()
    else:
      self._WriteFile(self._saved_command_line_file_contents)

  def _ReadFile(self):
    return self._adb.device().ReadFile(self.command_line_file, as_root=True)

  def _WriteFile(self, contents):
    self._adb.device().WriteFile(self.command_line_file, contents, as_root=True)

  def _RemoveFile(self):
    self._adb.device().RunShellCommand(['rm', '-f', self.command_line_file],
                                       as_root=True, check_return=True)
