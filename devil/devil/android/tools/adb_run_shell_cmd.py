#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import logging
import sys

from devil.android import device_blacklist
from devil.android import device_errors
from devil.android import device_utils
from devil.utils import run_tests_helper


def main():
  parser = argparse.ArgumentParser(
      'Run an adb shell command on selected devices')
  parser.add_argument('cmd', help='Adb shell command to run.', nargs="+")
  parser.add_argument('-d', '--device', action='append', dest='devices',
                      help='Device to run cmd on. Runs on all devices if not '
                           'specified. Set multiple times for multiple devices')
  parser.add_argument('-v', '--verbose', default=0, action='count',
                      help='Verbose level (multiple times for more)')
  parser.add_argument('--blacklist-file', help='Device blacklist file.')
  parser.add_argument('--as-root', action='store_true', help='Run as root.')
  parser.add_argument('--json-output',
                      help='File to dump json output to.')
  args = parser.parse_args()
  run_tests_helper.SetLogLevel(args.verbose)

  args.blacklist_file = device_blacklist.Blacklist(
      args.blacklist_file) if args.blacklist_file else None
  attached_devices = device_utils.DeviceUtils.HealthyDevices(
      blacklist=args.blacklist_file)

  if args.devices:
    selected_devices = []
    attached_devices = {str(d): d for d in attached_devices}
    for serial in args.devices:
      if serial in attached_devices:
        selected_devices.append(attached_devices[serial])
      else:
        logging.warning('Specified device %s not found.', serial)
  else:
    selected_devices = attached_devices

  if not selected_devices:
    raise device_errors.NoDevicesError

  p_out = (device_utils.DeviceUtils.parallel(selected_devices).RunShellCommand(
      args.cmd, large_output=True, as_root=args.as_root, check_return=True)
      .pGet(None))

  data = {}
  for device, output in zip(selected_devices, p_out):
    for line in output:
      print '%s: %s' %(device, line)
    data[str(device)] = output

  if args.json_output:
    with open(args.json_output, 'w') as f:
      json.dump(data, f)

  return 0


if __name__ == '__main__':
  sys.exit(main())
