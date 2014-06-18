# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import empty_timeline_data_importer
from telemetry.timeline import tracing_timeline_data


class EmptyTimelineDataImporterTest(unittest.TestCase):
  def testCanImportEmptyTimelineData(self):
    # We can import empty lists and empty string wrapped in subclasses of
    # TimelineData
    self.assertTrue(
        empty_timeline_data_importer.EmptyTimelineDataImporter.CanImport(
            tracing_timeline_data.TracingTimelineData([])))
    self.assertTrue(
        empty_timeline_data_importer.EmptyTimelineDataImporter.CanImport(
            tracing_timeline_data.TracingTimelineData('')))

  def testCannotImportNonEmptyTimelineData(self):
    # We can't import non-empty TimelineData objects
    self.assertFalse(
        empty_timeline_data_importer.EmptyTimelineDataImporter.CanImport(
            tracing_timeline_data.TracingTimelineData([1,2,3])))

  def testCannotImportEmptyRawData(self):
    # We can't import raw data (not wrapped in a TimelineData object)
    self.assertFalse(
        empty_timeline_data_importer.EmptyTimelineDataImporter.CanImport([]))
    self.assertFalse(
        empty_timeline_data_importer.EmptyTimelineDataImporter.CanImport(''))
