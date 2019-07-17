# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from devil import devil_env
from devil.android import device_blacklist
from devil.android import device_errors
from devil.android import device_utils


def AddEnvironmentArguments(parser):
  """Adds environment-specific arguments to the provided parser.

  After adding these arguments, you must pass the user-specified values when
  initializing devil. See the InitializeEnvironment() to determine how to do so.

  Args:
    parser: an instance of argparse.ArgumentParser
  """
  parser.add_argument(
      '--adb-path', type=os.path.realpath,
      help='Path to the adb binary')


def InitializeEnvironment(args):
  """Initializes devil based on the args added by AddEnvironmentArguments().

  This initializes devil, and configures it to use the adb binary specified by
  the '--adb-path' flag (if provided by the user, otherwise this defaults to
  devil's copy of adb). Although this is one possible way to initialize devil,
  you should check if your project has prefered ways to initialize devil (ex.
  the chromium project uses devil_chromium.Initialize() to have different
  defaults for dependencies).

  This method requires having previously called AddEnvironmentArguments() on the
  relevant argparse.ArgumentParser.

  Note: you should only initialize devil once, and subsequent calls to any
  method wrapping devil_env.config.Initialize() will have no effect.

  Args:
    args: the parsed args returned by an argparse.ArgumentParser
  """
  devil_dynamic_config = devil_env.EmptyConfig()
  if args.adb_path:
    devil_dynamic_config['dependencies'].update(
        devil_env.LocalConfigItem(
            'adb', devil_env.GetPlatform(), args.adb_path))

  devil_env.config.Initialize(configs=[devil_dynamic_config])


def AddDeviceArguments(parser):
  """Adds device and blacklist arguments to the provided parser.

  Args:
    parser: an instance of argparse.ArgumentParser
  """
  parser.add_argument(
      '-d', '--device', dest='devices', action='append',
      help='Serial number of the Android device to use. (default: use all)')
  parser.add_argument('--blacklist-file', help='Device blacklist JSON file.')


def GetDevices(requested_devices, blacklist_file):
  """Gets a list of healthy devices matching the given parameters."""
  if not isinstance(blacklist_file, device_blacklist.Blacklist):
    blacklist_file = (device_blacklist.Blacklist(blacklist_file)
                      if blacklist_file
                      else None)

  devices = device_utils.DeviceUtils.HealthyDevices(blacklist_file)
  if not devices:
    raise device_errors.NoDevicesError()
  elif requested_devices:
    requested = set(requested_devices)
    available = set(str(d) for d in devices)
    missing = requested.difference(available)
    if missing:
      raise device_errors.DeviceUnreachableError(next(iter(missing)))
    return sorted(device_utils.DeviceUtils(d)
                  for d in available.intersection(requested))
  else:
    return devices

