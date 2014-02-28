# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineData(object):
  """ Subclasses of TimelineData carry timeline data from a source
  (e.g. tracing, profiler, etc.) to the corresponding timeline importer.
  """
  def Serialize(self, f):
    """Serializes the event data to a file-like object"""
    pass

  def EventData(self):
    """Return the event data in a format that the corresponding timeline
    importer understands"""
    pass
