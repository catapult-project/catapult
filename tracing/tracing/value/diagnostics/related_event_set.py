# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from tracing.value.diagnostics import diagnostic


class RelatedEventSet(diagnostic.Diagnostic):
  __slots__ = '_events_by_stable_id',

  def __init__(self):
    super(RelatedEventSet, self).__init__()
    self._events_by_stable_id = {}

  def Add(self, event):
    self._events_by_stable_id[event['stableId']] = event

  def __len__(self):
    return len(self._events_by_stable_id)

  def __iter__(self):
    for event in self._events_by_stable_id.values():
      yield event

  @staticmethod
  def FromDict(d):
    result = RelatedEventSet()
    for event in d['events']:
      result.Add(event)
    return result

  def _AsDictInto(self, d):
    d['events'] = [event for event in self]
