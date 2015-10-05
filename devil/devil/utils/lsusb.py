# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from pylib import cmd_helper

_INDENTATION_RE = re.compile(r'^( *)')
_LSUSB_BUS_DEVICE_RE = re.compile(r'^Bus (\d{3}) Device (\d{3}):')
_LSUSB_ENTRY_RE = re.compile(r'^ *([^ ]+) +([^ ]+) *([^ ].*)?$')
_LSUSB_GROUP_RE = re.compile(r'^ *([^ ]+.*):$')

_USBDEVFS_RESET = ord('U') << 8 | 20


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


def get_lsusb_serial(device):
  return device.get('Device Descriptor', {}).get('iSerial', {}).get('_desc')


def get_android_devices():
  return [serial for serial in (get_lsusb_serial(d) for d in lsusb())
          if serial]

