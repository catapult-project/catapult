# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class RetainingEdge(object):
  """Data structure for representing a retainer relationship between objects.

  Attributes:
    from_object_id: int, id of the object which is the start point of this
        RetainingEdge.  Used when the corresponding LiveHeapObject object is not
        yet contstructed.
    to_object_id: int, id of the object which is the end point of this
        RetainingEdge. Used when the corresponding LiveHeapObject object is not
        yet contstructed.
    from_object: LiveHeapObject, the start point of this RetainingEdge.
    to_object: LiveHeapObject, the end point of this RetainingEdge.
    type_string: str, the type of the RetainingEdge.
    name_string: str, the JavaScript attribute name this RetainingEdge
        represents.
  """

  def __init__(self, from_object_id, to_object_id, type_string, name_string):
    """Initializes the RetainingEdge object.

    Args:
      from_object_id: int, id of the object which is the start point of this
          RetainingEdge. Used when the corresponding LiveHeapObject object is
          not yet contstructed.
      to_object_id: int, id of the object which is the end point of this
          RetainingEdge. Used when the corresponding LiveHeapObject object is
          not yet contstructed.
      type_string: str, the type of the RetainingEdge.
      name_string: str, the JavaScript attribute name this RetainingEdge
          represents.
    """
    self.from_object_id = from_object_id
    self.to_object_id = to_object_id
    self.from_object = {}
    self.to_object = {}
    self.type_string = type_string
    self.name_string = name_string

  def SetFromObject(self, obj):
    self.from_object = obj
    return self

  def SetToObject(self, obj):
    self.to_object = obj
    return self

  def __str__(self):
    return 'RetainingEdge(' + self.type_string + ' ' + self.name_string + ')'
