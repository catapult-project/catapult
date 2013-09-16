# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class LiveHeapObject(object):
  """Data structure for representing an object in the heap snapshot.

  Attributes:
    object_id: int, identifier for the object.
    type_string: str, describes the type of the node.
    class_name: str, describes the class of the JavaScript object
        represented by this LiveHeapObject.
    edges_to: [RetainingEdge], edges whose end point this LiveHeapObject is.
    edges_from: [RetainingEdge], edges whose start point this LiveHeapObject is.
    string: str, for string LiveHeapObjects, contains the string the
        LiveHeapObject represents. Empty string for LiveHeapObjects which are
        not strings.
    name: str, how to refer to this LiveHeapObject.
  """

  def __init__(self, object_id, type_string, class_name):
    """Initializes the LiveHeapObject object.

    Args:
      object_id: int, identifier for the LiveHeapObject.
      type_string: str, the type of the node.
      class_name: str, the class of the object this LiveHeapObject represents.
    """
    self.object_id = object_id
    self.type_string = type_string
    self.class_name = class_name
    self.edges_to = []
    self.edges_from = []
    self.string = ''
    self.name = ''

  def AddEdgeTo(self, edge):
    """Associates an Edge with the LiveHeapObject (the end point).

    Args:
      edge: Edge, an edge whose end point this LiveHeapObject is.
    """
    self.edges_to.append(edge)

  def AddEdgeFrom(self, edge):
    """Associates an Edge with the LiveHeapObject (the start point).

    Args:
      edge: Edge, an edge whose start point this LiveHeapObject is.
    """
    self.edges_from.append(edge)

  def __str__(self):
    prefix = 'LiveHeapObject(' + str(self.object_id) + ' '
    if self.type_string == 'object':
      return prefix + self.class_name + ')'
    return prefix + self.type_string + ')'
