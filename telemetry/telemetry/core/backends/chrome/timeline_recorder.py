# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineRecorder(object):
  """Interface for classes that can record timeline raw events."""
  def Start(self):
    """Starts recording."""
    raise NotImplementedError

  def Stop(self):
    """Stops recording and returns timeline event data."""
    raise NotImplementedError
