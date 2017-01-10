# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pipes

from devil.android import flag_changer  # pylint: disable=import-error


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
          device, backend_settings, startup_args):
        # Something to run while the command line flags are set appropriately.
  """
  def __init__(self, device, backend_settings, startup_args):
    cmdline_file = backend_settings.GetCommandLineFile(device.IsUserBuild())
    self._flag_changer = flag_changer.FlagChanger(device, cmdline_file)
    self._args = [_QuoteIfNeeded(arg) for arg in startup_args]

  def __enter__(self):
    self._flag_changer.ReplaceFlags(self._args)

  def __exit__(self, *args):
    self._flag_changer.Restore()
