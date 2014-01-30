# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class EmptyTraceImporter(object):
  """Imports empty traces."""
  def __init__(self, model, event_data, import_priority=0):
    pass

  @staticmethod
  def CanImport(event_data):
    if isinstance(event_data, list):
      return len(event_data) == 0
    elif isinstance(event_data, basestring):
      return len(event_data) == 0
    return False

  def ImportEvents(self):
    pass

  def FinalizeImport(self):
    pass
