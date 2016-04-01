# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PLUGABLE_7PORT_LAYOUT = {1:7,
                         2:6,
                         3:5,
                         4:{1:4, 2:3, 3:2, 4:1}}

class HubType(object):
  def __init__(self, id_func, port_mapping):
    """Defines a type of hub.

    Args:
      id_func: [USBNode -> bool] is a function that can be run on a node
        to determine if the node represents this type of hub.
      port_mapping: [dict(int:(int|dict))] maps virtual to physical port
        numbers. For instance, {3:1, 1:2, 2:3} means that virtual port 3
        corresponds to physical port 1, virtual port 1 corresponds to physical
        port 2, and virtual port 2 corresponds to physical port 3. In the
        case of hubs with "internal" topology, this is represented by nested
        maps. For instance, {1:{1:1,2:2},2:{1:3,2:4}} means, e.g. that the
        device plugged into physical port 3 will show up as being connected
        to port 1, on a device which is connected to port 2 on the hub.
    """
    self._id_func = id_func
    # v2p = "virtual to physical" ports
    self._v2p_port = port_mapping

  def IsType(self, node):
    """Determines if the given Node is a hub of this type.

    Args:
      node: [USBNode] Node to check.
    """
    return self._id_func(node)

  def GetPhysicalPortToNodeTuples(self, node):
    """Gets devices connected to the physical ports on a hub of this type.

    Args:
      node: [USBNode] Node representing a hub of this type.

    Yields:
      A series of (int, USBNode) tuples giving a physical port
      and the USBNode connected to it.

    Raises:
      ValueError: If the given node isn't a hub of this type.
    """
    if self.IsType(node):
      for res in self._GppHelper(node, self._v2p_port):
        yield res
    else:
      raise ValueError('Node must be a hub of this type')

  def _GppHelper(self, node, mapping):
    """Helper function for GetPhysicalPortToNodeMap.

    Gets devices connected to physical ports, based on device tree
    rooted at the given node and the mapping between virtual and physical
    ports.

    Args:
      node: [USBNode] Root of tree to search for devices.
      mapping: [dict] Mapping between virtual and physical ports.

    Yields:
      A series of (int, USBNode) tuples giving a physical port
      and the Node connected to it.
    """
    for (virtual, physical) in mapping.iteritems():
      if node.HasPort(virtual):
        if isinstance(physical, dict):
          for res in self._GppHelper(node.PortToDevice(virtual), physical):
            yield res
        else:
          yield (physical, node.PortToDevice(virtual))

def _is_plugable_7port_hub(node):
  """Check if a node is a Plugable 7-Port Hub
  (Model USB2-HUB7BC)
  The topology of this device is a 4-port hub,
  with another 4-port hub connected on port 4.
  """
  if '1a40:0101' not in node.desc:
    return False
  if not node.HasPort(4):
    return False
  return '1a40:0101' in node.PortToDevice(4).desc

PLUGABLE_7PORT = HubType(_is_plugable_7port_hub, PLUGABLE_7PORT_LAYOUT)

def GetHubType(type_name):
  if type_name == 'plugable_7port':
    return PLUGABLE_7PORT
  else:
    raise ValueError('Invalid hub type')
