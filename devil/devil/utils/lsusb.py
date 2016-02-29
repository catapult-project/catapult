# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from devil.utils import cmd_helper

_COULDNT_OPEN_ERROR_RE = re.compile(r'Couldn\'t open device.*')
_INDENTATION_RE = re.compile(r'^( *)')
_LSUSB_BUS_DEVICE_RE = re.compile(r'^Bus (\d{3}) Device (\d{3}): (.*)')
_LSUSB_ENTRY_RE = re.compile(r'^ *([^ ]+) +([^ ]+) *([^ ].*)?$')
_LSUSB_GROUP_RE = re.compile(r'^ *([^ ]+.*):$')


def _lsusbv_on_device(bus_id, dev_id):
  """Calls lsusb -v on device."""
  _, raw_output = cmd_helper.GetCmdStatusAndOutputWithTimeout(
      ['lsusb', '-v', '-s', '%s:%s' % (bus_id, dev_id)], timeout=10)

  device = {'bus': bus_id, 'device': dev_id}
  depth_stack = [device]

  # TODO(jbudorick): Add documentation for parsing.
  for line in raw_output.splitlines():
    # Ignore blank lines.
    if not line:
      continue
    # Filter out error mesage about opening device.
    if _COULDNT_OPEN_ERROR_RE.match(line):
      continue
    # Find start of device information.
    m = _LSUSB_BUS_DEVICE_RE.match(line)
    if m:
      if m.group(1) != bus_id:
        logging.warning(
            'Expected bus_id value: %r, seen %r', bus_id, m.group(1))
      if m.group(2) != dev_id:
        logging.warning(
            'Expected dev_id value: %r, seen %r', dev_id, m.group(2))
      device['desc'] = m.group(3)
      continue

    indent_match = _INDENTATION_RE.match(line)
    if not indent_match:
      continue

    depth = 1 + len(indent_match.group(1)) / 2
    if depth > len(depth_stack):
      logging.error(
          'lsusb parsing error: unexpected indentation: "%s"', line)
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

  return device

def lsusb():
  """Call lsusb and return the parsed output."""
  _, lsusb_list_output = cmd_helper.GetCmdStatusAndOutputWithTimeout(
      ['lsusb'], timeout=10)
  devices = []
  for line in lsusb_list_output.splitlines():
    m = _LSUSB_BUS_DEVICE_RE.match(line)
    if m:
      bus_num = m.group(1)
      dev_num = m.group(2)
      try:
        devices.append(_lsusbv_on_device(bus_num, dev_num))
      except cmd_helper.TimeoutError:
        # Will be blacklisted if it is in expected device file, but times out.
        logging.info('lsusb -v %s:%s timed out.', bus_num, dev_num)
  return devices

def raw_lsusb():
  return cmd_helper.GetCmdOutput(['lsusb'])

def get_lsusb_serial(device):
  try:
    return device['Device Descriptor']['iSerial']['_desc']
  except KeyError:
    return None

def get_android_devices():
  return [serial for serial in (get_lsusb_serial(d) for d in lsusb())
          if serial]
