# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import subprocess
import sys


class OptionParserIgnoreErrors(optparse.OptionParser):
  """Wrapper for OptionParser that ignores errors and produces no output."""

  def error(self, msg):
    pass

  def exit(self, status=0, msg=None):
    pass

  def print_usage(self, out_file=None):
    pass

  def print_help(self, out_file=None):
    pass

  def print_version(self, out_file=None):
    pass


def add_adb_serial(adb_command, device_serial):
  if device_serial is not None:
    adb_command.insert(1, device_serial)
    adb_command.insert(1, '-s')


def construct_adb_shell_command(shell_args, device_serial):
  adb_command = ['adb', 'shell', ' '.join(shell_args)]
  add_adb_serial(adb_command, device_serial)
  return adb_command


def run_adb_shell(shell_args, device_serial):
  """Runs "adb shell" with the given arguments.

  Args:
    shell_args: array of arguments to pass to adb shell.
    device_serial: if not empty, will add the appropriate command-line
        parameters so that adb targets the given device.
  Returns:
    A tuple containing the adb output (stdout & stderr) and the return code
    from adb.  Will exit if adb fails to start.
  """
  adb_command = construct_adb_shell_command(shell_args, device_serial)

  adb_output = []
  adb_return_code = 0
  try:
    adb_output = subprocess.check_output(adb_command, stderr=subprocess.STDOUT,
                                         shell=False, universal_newlines=True)
  except OSError as error:
    # This usually means that the adb executable was not found in the path.
    print >> sys.stderr, ('\nThe command "%s" failed with the following error:'
                          % ' '.join(adb_command))
    print >> sys.stderr, '    %s' % str(error)
    print >> sys.stderr, 'Is adb in your path?'
    adb_return_code = error.errno
    adb_output = error
  except subprocess.CalledProcessError as error:
    # The process exited with an error.
    adb_return_code = error.returncode
    adb_output = error.output

  return (adb_output, adb_return_code)


def get_device_sdk_version():
  """Uses adb to attempt to determine the SDK version of a running device."""

  getprop_args = ['getprop', 'ro.build.version.sdk']

  # get_device_sdk_version() is called before we even parse our command-line
  # args.  Therefore, parse just the device serial number part of the
  # command-line so we can send the adb command to the correct device.
  parser = OptionParserIgnoreErrors()
  parser.add_option('-e', '--serial', dest='device_serial', type='string')
  options, unused_args = parser.parse_args()  # pylint: disable=unused-variable

  success = False

  adb_output, adb_return_code = run_adb_shell(getprop_args,
                                              options.device_serial)

  if adb_return_code == 0:
    # ADB may print output other than the version number (e.g. it chould
    # print a message about starting the ADB server).
    # Break the ADB output into white-space delimited segments.
    parsed_output = str.split(adb_output)
    if parsed_output:
      # Assume that the version number is the last thing printed by ADB.
      version_string = parsed_output[-1]
      if version_string:
        try:
          # Try to convert the text into an integer.
          version = int(version_string)
        except ValueError:
          version = -1
        else:
          success = True

  if not success:
    print >> sys.stderr, (
        '\nThe command "%s" failed with the following message:'
        % ' '.join(getprop_args))
    print >> sys.stderr, adb_output
    sys.exit(1)

  return version
