# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class EventStats(object):
  def __init__(self, src_event_name, result_name, result_description):
    self.src_event_name = src_event_name
    self.result_name = result_name
    self.result_description = result_description
    self.thread_duration = 0.0
    self.thread_duration_inside_idle = 0.0

  @property
  def thread_duration_outside_idle(self):
    return self.thread_duration - self.thread_duration_inside_idle


def _FindEventStats(event_stats_list, event_name):
  for event_stats in event_stats_list:
    if event_stats.src_event_name == event_name:
      return event_stats
  return None


def _IsDescendentOfIdleNotification(event):
  parent = event.parent_slice
  while parent:
    if parent.name == 'V8.GCIdleNotification':
      return True
    parent = parent.parent_slice
  return False

class V8Stats(object):
  def __init__(self, renderer_thread, interaction_records):
    self.all_event_stats = [
        EventStats('V8.GCIncrementalMarking',
                   'incremental_marking',
                   'total thread duration spent in incremental marking steps'),
        EventStats('V8.GCScavenger',
                   'scavenger',
                   'total thread duration spent in scavenges'),
        EventStats('V8.GCCompactor',
                   'mark_compactor',
                   'total thread duration spent in mark-sweep-compactor')]

    # Find all GC events contained in an interaction record
    for event in renderer_thread.IterAllSlices():
      event_stats = _FindEventStats(self.all_event_stats, event.name)
      if not event_stats:
        continue
      for r in interaction_records:
        if not r.GetBounds().ContainsInterval(event.start, event.end):
          continue
        event_stats.thread_duration += event.thread_duration
        if _IsDescendentOfIdleNotification(event):
          event_stats.thread_duration_inside_idle += event.thread_duration

  @property
  def total_gc_thread_duration(self):
    return sum(x.thread_duration for x in self.all_event_stats)

  @property
  def total_gc_thread_duration_outside_idle(self):
    return sum(x.thread_duration_outside_idle for x in self.all_event_stats)
