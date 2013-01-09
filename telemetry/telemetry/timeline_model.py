# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class TimelineModel(object):
  def __init__(self):
    self._events = []
    self._frozen = False

  def AddEvent(self, event):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")
    self._events.extend(
      event.GetAllChildrenRecursive(include_self=True))

  def DidFinishRecording(self):
    self._frozen = True

  def GetAllEvents(self):
    return self._events

  def GetAllOfName(self, name):
    return [e for e in self._events if e.name == name]
