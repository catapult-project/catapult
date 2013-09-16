# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.core.heap import live_heap_object
from telemetry.core.heap import retaining_edge

class ChromeJsHeapSnapshotParser(object):
  """ Parser for the heap snapshot.

  The heap snapshot JSON format is defined by HeapSnapshotJSONSerializer in V8.

  The snapshot contains a list of integers describing nodes (types, names, etc.)
  and a list of integers describing edges (types, the node the edge points to,
  etc.) and a string table. All strings are expressed as indices to the string
  table.

  In addition, the snapshot contains meta information describing the data fields
  for nodes and the data fields for edges.

  Attributes:
    _node_dict: {int -> LiveHeapObject}, maps integer ids to LiveHeapObject
        objects.
    _node_list: [int], the raw node data of the heap snapshot.
    _edge_list: [int], the raw edge data of the heap snapshot.
    _node_types: [str], the possible node types in the heap snapshot.
    _edge_types: [str], the possible edge types in the heap snapshot.
    _node_fields: [str], the fields present in the heap snapshot for each node.
    _edge_fields: [str], the fields present in the heap snapshot for each node.
    _node_type_ix: int, index of the node type field.
    _node_name_ix: int, index of the node name field.
    _node_id_ix: int, index of the node id field.
    _node_edge_count_ix: int, index of the node edge count field.
    _node_field_count: int, number of node fields.
    _edge_type_ix: int, index of the edge type field.
    _edge_name_or_ix_ix: int, index of the "edge name or index" field.
    _edge_to_node_ix: int, index of the "to node for an edge" field.
    _edge_field_count: int, number of edge fields.
  """

  def __init__(self, raw_data):
    heap = json.loads(raw_data)
    self._node_dict = {}

    # Read the snapshot components (nodes, edges, strings, metadata).
    self._node_list = heap['nodes']
    self._edge_list = heap['edges']
    self._strings = heap['strings']

    self._node_types = heap['snapshot']['meta']['node_types'][0]
    self._edge_types = heap['snapshot']['meta']['edge_types'][0]
    node_fields = heap['snapshot']['meta']['node_fields']
    edge_fields = heap['snapshot']['meta']['edge_fields']

    # Find the indices of the required node and edge fields based on the
    # metadata.
    self._node_type_ix = node_fields.index('type')
    self._node_name_ix = node_fields.index('name')
    self._node_id_ix = node_fields.index('id')
    self._node_edge_count_ix = node_fields.index('edge_count')
    self._node_field_count = len(node_fields)

    self._edge_type_ix = edge_fields.index('type')
    self._edge_name_or_ix_ix = edge_fields.index('name_or_index')
    self._edge_to_node_ix = edge_fields.index('to_node')
    self._edge_field_count = len(edge_fields)

    self._ParseSnapshot()

  @staticmethod
  def CanImport(raw_data):
    heap = json.loads(raw_data)
    if ('nodes' not in heap or 'edges' not in heap or 'strings' not in heap or
        'snapshot' not in heap or 'meta' not in heap['snapshot']):
      return False
    meta = heap['snapshot']['meta']
    if ('node_types' not in meta or 'edge_types' not in meta or
        'node_fields' not in meta or 'edge_fields' not in meta):
      return False
    node_fields = meta['node_fields']
    edge_fields = meta['edge_fields']
    if ('type' not in node_fields or 'name' not in node_fields or
        'id' not in node_fields or 'edge_count' not in node_fields):
      return False
    if ('type' not in edge_fields or 'name_or_index' not in edge_fields or
        'to_node' not in edge_fields):
      return False
    return True

  def GetAllLiveHeapObjects(self):
    return self._node_dict.values()

  @staticmethod
  def LiveHeapObjectToJavaScript(heap_object):
    return heap_object.name or str(heap_object)

  @staticmethod
  def RetainingEdgeToJavaScript(edge):
    if edge.type_string == 'property':
      return '.' + edge.name_string
    if edge.type_string == 'element':
      return '[' + edge.name_string + ']'
    return str(edge)

  def _ParseSnapshot(self):
    """Parses the stored JSON snapshot data.

    Fills in self._node_dict with LiveHeapObject objects constructed based on
    the heap snapshot. The LiveHeapObject objects contain the associated
    RetainingEdge objects.
    """
    edge_start_ix = 0
    for ix in xrange(0, len(self._node_list), self._node_field_count):
      edge_start_ix = self._ReadNodeFromIndex(ix, edge_start_ix)

    # Add pointers to the endpoints to the edges, and associate the edges with
    # the "to" nodes.
    for node_id in self._node_dict:
      n = self._node_dict[node_id]
      for e in n.edges_from:
        self._node_dict[e.to_object_id].AddEdgeTo(e)
        e.SetFromObject(n)
        e.SetToObject(self._node_dict[e.to_object_id])

  def _ReadNodeFromIndex(self, ix, edges_start):
    """Reads the data for a node from the heap snapshot.

    If the index contains an interesting node, constructs a Node object and adds
    it to self._node_dict.

    Args:
      ix: int, index into the self._node_list array.
      edges_start: int, the index of the edge array where the edges for the node
          start.
    Returns:
      int, the edge start index for the next node.

    Raises:
      Exception: The node list of the snapshot is malformed.
    """
    if ix + self._node_field_count > len(self._node_list):
      raise Exception('Snapshot node list too short')

    type_ix = self._node_list[ix + self._node_type_ix]
    type_string = self._node_types[int(type_ix)]

    # edges_end is noninclusive (the index of the first edge that is not part of
    # this node).
    edge_count = self._node_list[ix + self._node_edge_count_ix]
    edges_end = edges_start + edge_count * self._edge_field_count

    if ChromeJsHeapSnapshotParser._IsNodeTypeUninteresting(type_string):
      return edges_end

    name_ix = self._node_list[ix + self._node_name_ix]
    node_id = self._node_list[ix + self._node_id_ix]

    def ConstructorName(type_string, node_name_ix):
      if type_string == 'object':
        return self._strings[int(node_name_ix)]
      return '(%s)' % type_string

    ctor_name = ConstructorName(type_string, name_ix)
    n = live_heap_object.LiveHeapObject(node_id, type_string, ctor_name)
    if type_string == 'string':
      n.string = self._strings[int(name_ix)]

    for edge_ix in xrange(edges_start, edges_end, self._edge_field_count):
      edge = self._ReadEdgeFromIndex(node_id, edge_ix)
      if edge:
        # The edge will be associated with the other endpoint when all the data
        # has been read.
        n.AddEdgeFrom(edge)

    self._node_dict[node_id] = n
    return edges_end

  @staticmethod
  def _IsNodeTypeUninteresting(type_string):
    """Helper function for filtering out nodes from the heap snapshot.

    Args:
      type_string: str, type of the node.
    Returns:
      bool, True if the node is of an uninteresting type and shouldn't be
          included in the heap snapshot analysis.
    """
    uninteresting_types = ('hidden', 'code', 'number', 'native', 'synthetic')
    return type_string in uninteresting_types

  @staticmethod
  def _IsEdgeTypeUninteresting(edge_type_string):
    """Helper function for filtering out edges from the heap snapshot.

    Args:
      edge_type_string: str, type of the edge.
    Returns:
      bool, True if the edge is of an uninteresting type and shouldn't be
          included in the heap snapshot analysis.
    """
    uninteresting_types = ('weak', 'hidden', 'internal')
    return edge_type_string in uninteresting_types

  def _ReadEdgeFromIndex(self, node_id, edge_ix):
    """Reads the data for an edge from the heap snapshot.

    Args:
      node_id: int, id of the node which is the starting point of the edge.
      edge_ix: int, index into the self._edge_list array.
    Returns:
      Edge, if the index contains an interesting edge, otherwise None.
    Raises:
      Exception: The node list of the snapshot is malformed.
    """
    if edge_ix + self._edge_field_count > len(self._edge_list):
      raise Exception('Snapshot edge list too short')

    edge_type_ix = self._edge_list[edge_ix + self._edge_type_ix]
    edge_type_string = self._edge_types[int(edge_type_ix)]

    if ChromeJsHeapSnapshotParser._IsEdgeTypeUninteresting(edge_type_string):
      return None

    child_name_or_ix = self._edge_list[edge_ix + self._edge_name_or_ix_ix]
    child_node_ix = self._edge_list[edge_ix + self._edge_to_node_ix]

    # The child_node_ix is an index into the node list. Read the actual
    # node information.
    child_node_type_ix = self._node_list[child_node_ix + self._node_type_ix]
    child_node_type_string = self._node_types[int(child_node_type_ix)]
    child_node_id = self._node_list[child_node_ix + self._node_id_ix]

    if ChromeJsHeapSnapshotParser._IsNodeTypeUninteresting(
        child_node_type_string):
      return None

    child_name_string = ''
    # For element nodes, the child has no name (only an index).
    if (edge_type_string == 'element' or
        int(child_name_or_ix) >= len(self._strings)):
      child_name_string = str(child_name_or_ix)
    else:
      child_name_string = self._strings[int(child_name_or_ix)]
    return retaining_edge.RetainingEdge(node_id, child_node_id,
                                        edge_type_string, child_name_string)
