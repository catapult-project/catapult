#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import fcntl
import logging
import re
import sys

from pylib import cmd_helper
from pylib.device import adb_wrapper
from pylib.device import device_errors
from pylib.utils import run_tests_helper

_INDENTATION_RE = re.compile(r'^( *)')
_LSUSB_BUS_DEVICE_RE = re.compile(r'^Bus (\d{3}) Device (\d{3}):')
_LSUSB_ENTRY_RE = re.compile(r'^ *([^ ]+) +([^ ]+) *([^ ].*)?$')
_LSUSB_GROUP_RE = re.compile(r'^ *([^ ]+.*):$')

_USBDEVFS_RESET = ord('U') << 8 | 20


def reset_usb(bus, device):
  """Reset the USB device with the given bus and device."""
  usb_file_path = '/dev/bus/usb/%03d/%03d' % (bus, device)
  with open(usb_file_path, 'w') as usb_file:
    logging.debug('fcntl.ioctl(%s, %d)', usb_file_path, _USBDEVFS_RESET)
    fcntl.ioctl(usb_file, _USBDEVFS_RESET)


def reset_android_usb(serial):
  """Reset the USB device for the given Android device."""
  lsusb_info = lsusb()

  bus = None
  device = None
  for device_info in lsusb_info:
    device_serial = _get_lsusb_serial(device)
    if device_serial == serial:
      bus = int(device_info.get('bus'))
      device = int(device_info.get('device'))

  if bus and device:
    reset_usb(bus, device)
  else:
    raise device_errors.DeviceUnreachableError(
        'Unable to determine bus or device for device %s' % serial)


def reset_all_android_devices():
  """Reset all USB devices that look like an Android device."""
  _reset_all_matching(lambda i: bool(_get_lsusb_serial(i)))


def _reset_all_matching(condition):
  lsusb_info = lsusb()
  for device_info in lsusb_info:
    if int(device_info.get('device')) != 1 and condition(device_info):
      bus = int(device_info.get('bus'))
      device = int(device_info.get('device'))
      try:
        reset_usb(bus, device)
        serial = _get_lsusb_serial(device_info)
        if serial:
          logging.info('Reset USB device (bus: %03d, device: %03d, serial: %s)',
              bus, device, serial)
        else:
          logging.info('Reset USB device (bus: %03d, device: %03d)',
              bus, device)
      except IOError:
        logging.error(
            'Failed to reset USB device (bus: %03d, device: %03d)',
            bus, device)


def lsusb():
  """Call lsusb and return the parsed output."""
  lsusb_raw_output = cmd_helper.GetCmdOutput(['lsusb', '-v'])
  device = None
  devices = []
  depth_stack = []
  for line in lsusb_raw_output.splitlines():
    if not line:
      if device:
        devices.append(device)
      device = None
      continue

    if not device:
      m = _LSUSB_BUS_DEVICE_RE.match(line)
      if m:
        device = {
          'bus': m.group(1),
          'device': m.group(2)
        }
        depth_stack = [device]
      continue

    indent_match = _INDENTATION_RE.match(line)
    if not indent_match:
      continue

    depth = 1 + len(indent_match.group(1)) / 2
    if depth > len(depth_stack):
      logging.error('lsusb parsing error: unexpected indentation: "%s"', line)
      continue

    while depth < len(depth_stack):
      depth_stack.pop()

    cur = depth_stack[-1]

    m = _LSUSB_GROUP_RE.match(line)
    if m:
      new_group = {}
      cur[m.group(1)] = new_group
      depth_stack.append(new_group)
      continue

    m = _LSUSB_ENTRY_RE.match(line)
    if m:
      new_entry = {
        '_value': m.group(2),
        '_desc': m.group(3),
      }
      cur[m.group(1)] = new_entry
      depth_stack.append(new_entry)
      continue

    logging.error('lsusb parsing error: unrecognized line: "%s"', line)

  if device:
    devices.append(device)

  return devices


def _get_lsusb_serial(device):
  return device.get('Device Descriptor', {}).get('iSerial', {}).get('_desc')


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose', action='count')
  parser.add_argument('-s', '--serial')
  parser.add_argument('--bus', type=int)
  parser.add_argument('--device', type=int)
  args = parser.parse_args()

  run_tests_helper.SetLogLevel(args.verbose)

  if args.serial:
    reset_android_usb(args.serial)
  elif args.bus and args.device:
    reset_usb(args.bus, args.device)
  else:
    parser.error('Unable to determine target. '
                 'Specify --serial or BOTH --bus and --device.')

  return 0


if __name__ == '__main__':
  sys.exit(main())

