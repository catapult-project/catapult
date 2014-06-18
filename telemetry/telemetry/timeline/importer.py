# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineImporter(object):
  """Interface for classes that can add events to
  a timeline model from an TimelineData."""
  def __init__(self, model, timeline_data, import_priority=0):
    self._model = model
    self._timeline_data = timeline_data
    self.import_priority = import_priority

  @staticmethod
  def CanImport(event_data_wrapper):
    """Returns true if the importer can process the given event data in the
    wrapper."""
    raise NotImplementedError

  def ImportEvents(self):
    """Processes the event data in the wrapper and creates and adds
    new timeline events to the model"""
    raise NotImplementedError

  def FinalizeImport(self):
    """Called after all other importers for the model are run."""
    raise NotImplementedError
