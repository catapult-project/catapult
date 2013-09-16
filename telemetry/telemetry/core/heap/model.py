# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.heap import chrome_js_heap_snapshot_parser

class Model(object):
  """ The heap snapshot model is a set of LiveHeapObjects. The LiveHeapObjects
  contain the RetainingEdge objects describing the relationships between the
  LiveHeapObjects."""

  def __init__(self, raw_data):
    if not chrome_js_heap_snapshot_parser.ChromeJsHeapSnapshotParser.CanImport(
        raw_data):
      raise ValueError("Cannot import snapshot data")
    parser = chrome_js_heap_snapshot_parser.ChromeJsHeapSnapshotParser(raw_data)
    self._all_live_heap_objects = parser.GetAllLiveHeapObjects()

  @property
  def all_live_heap_objects(self):
    return self._all_live_heap_objects
