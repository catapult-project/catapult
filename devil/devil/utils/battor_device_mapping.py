#!/usr/bin/python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import collections

from battor import battor_error
from devil.utils import find_usb_devices
from devil.utils import usb_hubs

def GetBattorList(device_tree_map):
  return [x for x in find_usb_devices.GetTTYList()
          if IsBattor(x, device_tree_map)]


def IsBattor(tty_string, device_tree_map):
  (bus, device) = find_usb_devices.GetBusDeviceFromTTY(tty_string)
  node = device_tree_map[bus].FindDeviceNumber(device)
  return '0403:6001' in node.desc


def GetBattorSerialNumbers(device_tree_map):
  for x in find_usb_devices.GetTTYList():
    if IsBattor(x, device_tree_map):
      (bus, device) = find_usb_devices.GetBusDeviceFromTTY(x)
      devnode = device_tree_map[bus].FindDeviceNumber(device)
      yield devnode.serial


def ReadSerialMapFile(filename):
  """Reads JSON file giving phone-to-battor serial number map.

  Parses a JSON file consisting of a list of items of the following form:
  [{'phone': <phone serial 1>, 'battor': <battor serial 1>},
  {'phone': <phone serial 2>, 'battor': <battor serial 2>}, ...]

  indicating which phone serial numbers should be matched with
  which BattOr serial numbers. Returns dictionary of the form:

  {<phone serial 1>: <BattOr serial 1>,
   <phone serial 2>: <BattOr serial 2>}

  Args:
      filename: Name of file to read.
  """
  result = {}
  with open(filename, 'r') as infile:
    in_dict = json.load(infile)
  for x in in_dict:
    result[x['phone']] = x['battor']
  return result

def WriteSerialMapFile(filename, serial_map):
  """Writes a map of phone serial numbers to BattOr serial numbers to file.

  Writes a JSON file consisting of a list of items of the following form:
  [{'phone': <phone serial 1>, 'battor': <battor serial 1>},
  {'phone': <phone serial 2>, 'battor': <battor serial 2>}, ...]

  indicating which phone serial numbers should be matched with
  which BattOr serial numbers. Mapping is based on the physical port numbers
  of the hubs that the BattOrs and phones are connected to.

  Args:
      filename: Name of file to write.
      serial_map: Serial map {phone: battor}
  """
  result = []
  for (phone, battor) in serial_map.iteritems():
    result.append({'phone': phone, 'battor': battor})
  with open(filename, 'w') as outfile:
    json.dump(result, outfile)

def GenerateSerialMap(hub_types=None):
  """Generates a map of phone serial numbers to BattOr serial numbers.

  Generates a dict of:
  {<phone serial 1>: <battor serial 1>,
   <phone serial 2>: <battor serial 2>}
  indicating which phone serial numbers should be matched with
  which BattOr serial numbers. Mapping is based on the physical port numbers
  of the hubs that the BattOrs and phones are connected to.

  Args:
      hub_types: List of hub types to check for.
      Defaults to ['plugable_7port']
  """
  hub_types = [usb_hubs.GetHubType(x)
               for x in hub_types or ['plugable_7port']]
  devtree = find_usb_devices.GetBusNumberToDeviceTreeMap()

  # List of serial numbers in the system that represent BattOrs.
  battor_serials = list(GetBattorSerialNumbers(devtree))

  # List of dictionaries, one for each hub, that maps the physical
  # port number to the serial number of that hub. For instance, in a 2
  # hub system, this could return [{1:'ab', 2:'cd'}, {1:'jkl', 2:'xyz'}]
  # where 'ab' and 'cd' are the phone serial numbers and 'jkl' and 'xyz'
  # are the BattOr serial numbers.
  port_to_serial = find_usb_devices.GetAllPhysicalPortToSerialMaps(
      hub_types, device_tree_map=devtree)

  class serials(object):
    def __init__(self):
      self.phone = None
      self.battor = None

  # Map of {physical port number: [phone serial #, BattOr serial #]. This
  # map is populated by executing the code below. For instance, in the above
  # example, after the code below is executed, port_to_devices would equal
  # {1: ['ab', 'jkl'], 2: ['cd', 'xyz']}
  port_to_devices = collections.defaultdict(serials)
  for hub in port_to_serial:
    for (port, serial) in hub.iteritems():
      if serial in battor_serials:
        if port_to_devices[port].battor is not None:
          raise battor_error.BattorError('Multiple BattOrs on same port number')
        else:
          port_to_devices[port].battor = serial
      else:
        if port_to_devices[port].phone is not None:
          raise battor_error.BattorError('Multiple phones on same port number')
        else:
          port_to_devices[port].phone = serial

  # Turn the port_to_devices map into a map of the form
  # {phone serial number: BattOr serial number}.
  result = {}
  for pair in port_to_devices.values():
    if pair.phone is None:
      raise battor_error.BattorError(
          'BattOr detected with no corresponding phone')
    if pair.battor is None:
      raise battor_error.BattorError(
          'Phone detected with no corresponding BattOr')
    result[pair.phone] = pair.battor
  return result

def GenerateSerialMapFile(filename, hub_types=None):
  """Generates a serial map file and writes it."""
  WriteSerialMapFile(filename, GenerateSerialMap(hub_types))

def _PhoneToPathMap(serial, serial_map, devtree):
  """Maps phone serial number to TTY path, assuming serial map is provided."""
  battor_serial = serial_map[serial]
  for tree in devtree.values():
    for node in tree.AllNodes():
      if isinstance(node, find_usb_devices.USBDeviceNode):
        if node.serial == battor_serial:
          bus_device_to_tty = find_usb_devices.GetBusDeviceToTTYMap()
          bus_device = (node.bus_num, node.device_num)
          try:
            return bus_device_to_tty[bus_device]
          except KeyError:
            raise battor_error.BattorError(
                'Device with given serial number not a BattOr '
                '(does not have TTY path)')


def GetBattorPathFromPhoneSerial(serial, serial_map=None,
                                 serial_map_file=None):
  """Gets the TTY path (e.g. '/dev/ttyUSB0')  to communicate with the BattOr.

  (1) If serial_map is given, it is treated as a dictionary mapping
  phone serial numbers to BattOr serial numbers. This function will get the
  TTY path for the given BattOr serial number.

  (2) If serial_map_file is given, it is treated as the name of a
  phone-to-BattOr mapping file (generated with GenerateSerialMapFile)
  and this will be loaded and used as the dict to map port numbers to
  BattOr serial numbers.

  You can only give one of serial_map and serial_map_file.

  Args:
    serial: Serial number of phone connected on the same physical port that
    the BattOr is connected to.
    serial_map: Map of phone serial numbers to BattOr serial numbers, given
    as a dictionary.
    serial_map_file: Map of phone serial numbers to BattOr serial numbers,
    given as a file.
    hub_types: List of hub types to check for. Used only if serial_map_file
    is None.

  Returns:
    Device string used to communicate with device.

  Raises:
    ValueError: If serial number is not given.
    BattorError: If BattOr not found or unexpected USB topology.
  """
  # If there's only one BattOr connected to the system, just use that one.
  # This allows for use on, e.g., a developer's workstation with no hubs.
  devtree = find_usb_devices.GetBusNumberToDeviceTreeMap()
  all_battors = GetBattorList(devtree)
  if len(all_battors) == 1:
    return '/dev/' + all_battors[0]

  if not serial:
    raise battor_error.BattorError(
        'Two or more BattOrs connected, no serial provided')

  if serial_map and serial_map_file:
    raise ValueError('Cannot specify both serial_map and serial_map_file')

  if serial_map_file:
    serial_map = ReadSerialMapFile(serial_map_file)

  tty_string = _PhoneToPathMap(serial, serial_map, devtree)

  if not tty_string:
    raise battor_error.BattorError(
        'No device with given serial number detected.')

  if IsBattor(tty_string, devtree):
    return '/dev/' + tty_string
  else:
    raise battor_error.BattorError(
        'Device with given serial number is not a BattOr.')
