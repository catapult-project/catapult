# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

from telemetry.core.heap import chrome_js_heap_snapshot_parser

class ChromeJsHeapSnapshotParserUnittest(unittest.TestCase):
  def _HeapSnapshotData(self, node_types, edge_types, node_fields, edge_fields,
                        node_list, edge_list, strings):
    """Helper for creating heap snapshot data."""
    return {'snapshot': {'meta': {'node_types': [node_types],
                                  'edge_types': [edge_types],
                                  'node_fields': node_fields,
                                  'edge_fields': edge_fields}},
            'nodes': node_list,
            'edges': edge_list,
            'strings': strings}

  def testParseSimpleSnapshot(self):
    # Create a snapshot containing 2 nodes and an edge between them.
    node_types = ['object']
    edge_types = ['property']
    node_fields = ['type', 'name', 'id', 'edge_count']
    edge_fields = ['type', 'name_or_index', 'to_node']
    node_list = [0, 0, 0, 1,
                 0, 1, 1, 0]
    edge_list = [0, 2, 4]
    strings = ['node1', 'node2', 'edge1']
    heap = self._HeapSnapshotData(node_types, edge_types, node_fields,
                                  edge_fields, node_list, edge_list, strings)
    objects = list(chrome_js_heap_snapshot_parser.ChromeJsHeapSnapshotParser(
        json.dumps(heap)).GetAllLiveHeapObjects())
    self.assertEqual(2, len(objects))
    if objects[0].edges_from:
      from_ix = 0
      to_ix = 1
    else:
      from_ix = 1
      to_ix = 0
    self.assertEqual('node1', objects[from_ix].class_name)
    self.assertEqual('node2', objects[to_ix].class_name)
    self.assertEqual(1, len(objects[from_ix].edges_from))
    self.assertEqual(0, len(objects[from_ix].edges_to))
    self.assertEqual(0, len(objects[to_ix].edges_from))
    self.assertEqual(1, len(objects[to_ix].edges_to))
    self.assertEqual('node1',
                     objects[from_ix].edges_from[0].from_object.class_name)
    self.assertEqual('node2',
                     objects[from_ix].edges_from[0].to_object.class_name)
    self.assertEqual('edge1', objects[from_ix].edges_from[0].name_string)
    self.assertEqual('node1', objects[to_ix].edges_to[0].from_object.class_name)
    self.assertEqual('node2', objects[to_ix].edges_to[0].to_object.class_name)
    self.assertEqual('edge1', objects[to_ix].edges_to[0].name_string)
