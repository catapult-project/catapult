# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
'''A container for timeline-based events and traces and can handle importing
raw event data from different sources. This model closely resembles that in the
trace_viewer project:
https://code.google.com/p/trace-viewer/
'''

from operator import attrgetter
import weakref

import telemetry.core.timeline.process as tracing_process
from telemetry.core import web_contents
from telemetry.core import browser

# Register importers for data
from telemetry.core.timeline import bounds
from telemetry.core.timeline import empty_trace_importer
from telemetry.core.timeline import inspector_importer
from telemetry.core.timeline import trace_event_importer

_IMPORTERS = [
    empty_trace_importer.EmptyTraceImporter,
    inspector_importer.InspectorTimelineImporter,
    trace_event_importer.TraceEventTimelineImporter
]


class MarkerMismatchError(Exception):
  def __init__(self):
    super(MarkerMismatchError, self).__init__(
        'Number or order of timeline markers does not match provided labels')


class MarkerOverlapError(Exception):
  def __init__(self):
    super(MarkerOverlapError, self).__init__(
        'Overlapping timeline markers found')


class TimelineModel(object):
  def __init__(self, event_data=None, shift_world_to_zero=True):
    self._bounds = bounds.Bounds()
    self._thread_time_bounds = {}
    self._processes = {}
    self._browser_process = None
    self._frozen = False
    self.import_errors = []
    self.metadata = []
    self.flow_events = []
    # Use a WeakKeyDictionary, because an ordinary dictionary could keep
    # references to Tab objects around until it gets garbage collected.
    # This would prevent telemetry from navigating to another page.
    self._core_object_to_timeline_container_map = weakref.WeakKeyDictionary()

    if event_data is not None:
      self.ImportTraces([event_data], shift_world_to_zero=shift_world_to_zero)

  @property
  def bounds(self):
    return self._bounds

  @property
  def thread_time_bounds(self):
    return self._thread_time_bounds

  @property
  def processes(self):
    return self._processes

  @property
  #pylint: disable=E0202
  def browser_process(self):
    return self._browser_process

  @browser_process.setter
  #pylint: disable=E0202
  def browser_process(self, browser_process):
    self._browser_process = browser_process

  def ImportTraces(self, traces, shift_world_to_zero=True):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")

    importers = []
    for event_data in traces:
      importers.append(self._CreateImporter(event_data))

    importers.sort(cmp=lambda x, y: x.import_priority - y.import_priority)

    for importer in importers:
      # TODO: catch exceptions here and add it to error list
      importer.ImportEvents()
    self.FinalizeImport(shift_world_to_zero, importers)

  def FinalizeImport(self, shift_world_to_zero=False, importers=None):
    if importers == None:
      importers = []
    self.UpdateBounds()
    if not self.bounds.is_empty:
      for process in self._processes.itervalues():
        process.AutoCloseOpenSlices(self.bounds.max,
                                    self.thread_time_bounds)

    for importer in importers:
      importer.FinalizeImport()

    for process in self.processes.itervalues():
      process.FinalizeImport()

    if shift_world_to_zero:
      self.ShiftWorldToZero()
    self.UpdateBounds()

    # Because of FinalizeImport, it would probably be a good idea
    # to prevent the timeline from from being modified.
    self._frozen = True

  def ShiftWorldToZero(self):
    self.UpdateBounds()
    if self._bounds.is_empty:
      return
    shift_amount = self._bounds.min
    for event in self.IterAllEvents():
      event.start -= shift_amount

  def UpdateBounds(self):
    self._bounds.Reset()
    for event in self.IterAllEvents():
      self._bounds.AddValue(event.start)
      self._bounds.AddValue(event.end)

    self._thread_time_bounds = {}
    for thread in self.GetAllThreads():
      self._thread_time_bounds[thread] = bounds.Bounds()
      for event in thread.IterEventsInThisContainer():
        if event.thread_start != None:
          self._thread_time_bounds[thread].AddValue(event.thread_start)
        if event.thread_end != None:
          self._thread_time_bounds[thread].AddValue(event.thread_end)

  def GetAllContainers(self):
    containers = []
    def Iter(container):
      containers.append(container)
      for container in container.IterChildContainers():
        Iter(container)
    for process in self._processes.itervalues():
      Iter(process)
    return containers

  def IterAllEvents(self):
    for container in self.GetAllContainers():
      for event in container.IterEventsInThisContainer():
        yield event

  def GetAllProcesses(self):
    return self._processes.values()

  def GetAllThreads(self):
    threads = []
    for process in self._processes.values():
      threads.extend(process.threads.values())
    return threads

  def GetAllEvents(self):
    return list(self.IterAllEvents())

  def GetAllEventsOfName(self, name, only_root_events=False):
    events = [e for e in self.IterAllEvents() if e.name == name]
    if only_root_events:
      return filter(lambda ev: ev.parent_slice == None, events)
    else:
      return events

  def GetEventOfName(self, name, only_root_events=False,
                     fail_if_more_than_one=False):
    events = self.GetAllEventsOfName(name, only_root_events)
    if len(events) == 0:
      raise Exception('No event of name "%s" found.' % name)
    if fail_if_more_than_one and len(events) > 1:
      raise Exception('More than one event of name "%s" found.' % name)
    return events[0]

  def GetOrCreateProcess(self, pid):
    if pid not in self._processes:
      assert not self._frozen
      self._processes[pid] = tracing_process.Process(self, pid)
    return self._processes[pid]

  def FindTimelineMarkers(self, timeline_marker_names):
    """Find the timeline events with the given names.

    If the number and order of events found does not match the names,
    raise an error.
    """
    # Make sure names are in a list and remove all None names
    if not isinstance(timeline_marker_names, list):
      timeline_marker_names = [timeline_marker_names]
    names = [x for x in timeline_marker_names if x is not None]

    # Gather all events that match the names and sort them.
    events = []
    name_set = set()
    for name in names:
      name_set.add(name)
    for name in name_set:
      events.extend(self.GetAllEventsOfName(name, True))
    events.sort(key=attrgetter('start'))

    # Check if the number and order of events matches the provided names,
    # and that the events don't overlap.
    if len(events) != len(names):
      raise MarkerMismatchError()
    for (i, event) in enumerate(events):
      if event.name != names[i]:
        raise MarkerMismatchError()
    for i in xrange(0, len(events)):
      for j in xrange(i+1, len(events)):
        if (events[j].start < events[i].start + events[i].duration):
          raise MarkerOverlapError()

    return events

  def GetRendererProcessFromTab(self, tab):
    return self._core_object_to_timeline_container_map[tab]

  def AddCoreObjectToContainerMapping(self, core_object, container):
    """ Add a mapping from a core object to a timeline container.

    Used for example to map a Tab to its renderer process in the timeline model.
    """
    assert(isinstance(core_object, web_contents.WebContents) or
           isinstance(core_object, browser.Browser))
    self._core_object_to_timeline_container_map[core_object] = container

  def _CreateImporter(self, event_data):
    for importer_class in _IMPORTERS:
      if importer_class.CanImport(event_data):
        return importer_class(self, event_data)
    raise ValueError("Could not find an importer for the provided event data")
