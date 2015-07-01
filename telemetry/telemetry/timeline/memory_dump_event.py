# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import posixpath
import re

from telemetry.timeline import event as timeline_event


class MmapCategory(object):
  _DEFAULT_CATEGORY = None

  def __init__(self, name, file_pattern, children=None):
    """A (sub)category for classifying memory maps.

    Args:
      name: A string to identify the category.
      file_pattern: A regex pattern, the category will aggregate memory usage
          for all mapped files matching this pattern.
      children: A list of MmapCategory objects, used to sub-categorize memory
          usage.
    """
    self.name = name
    self._file_pattern = re.compile(file_pattern) if file_pattern else None
    self._children = list(children) if children else None

  @classmethod
  def DefaultCategory(cls):
    """An implicit 'Others' match-all category with no children."""
    if cls._DEFAULT_CATEGORY is None:
      cls._DEFAULT_CATEGORY = cls('Others', None)
    return cls._DEFAULT_CATEGORY

  def Match(self, mapped_file):
    """Test whether a mapped file matches this category."""
    return (self._file_pattern is None
            or bool(self._file_pattern.search(mapped_file)))

  def GetMatchingChild(self, mapped_file):
    """Get the first matching sub-category for a given mapped file.

    Returns None if the category has no children, or the DefaultCategory if
    it does have children but none of them match.
    """
    if not self._children:
      return None
    for child in self._children:
      if child.Match(mapped_file):
        return child
    return type(self).DefaultCategory()


ROOT_CATEGORY = MmapCategory('/', None, [
  MmapCategory('Android', r'^\/dev\/ashmem(?!\/libc malloc)', [
    MmapCategory('Java runtime', r'^\/dev\/ashmem\/dalvik-.*$', [
      MmapCategory('Spaces', r'\bspace', [
        MmapCategory('Normal', r'(alloc)|(main)'),
        MmapCategory('Large', r'large.object'),
        MmapCategory('Zygote', r'zygote'),
        MmapCategory('Non-moving', r'non.moving')
      ]),
      MmapCategory('Linear Alloc', r'LinearAlloc'),
      MmapCategory('Indirect Reference Table', r'indirect.ref'),
      MmapCategory('Cache', 'jit-code-cache'),
      MmapCategory('Accounting', None)
    ]),
    MmapCategory('Cursor', r'CursorWindow'),
    MmapCategory('Ashmem', None)
  ]),
  MmapCategory('Native heap',
               r'^((\[heap\])|(\[anon:)|(\/dev\/ashmem\/libc malloc)|$)'),
  MmapCategory('Stack', r'^\[stack'),
  MmapCategory('Files',
               r'\.((((so)|(jar)|(apk)|(ttf)|(odex)|(oat)|(arg))$)|(dex))', [
    MmapCategory('so', r'\.so$'),
    MmapCategory('jar', r'\.jar$'),
    MmapCategory('apk', r'\.apk$'),
    MmapCategory('ttf', r'\.ttf$'),
    MmapCategory('dex', r'\.((dex)|(odex$))'),
    MmapCategory('oat', r'\.oat$'),
    MmapCategory('art', r'\.art$'),
  ]),
  MmapCategory('Devices', r'(^\/dev\/)|(anon_inode:dmabuf)', [
    MmapCategory('GPU', r'\/((nv)|(mali)|(kgsl))'),
    MmapCategory('DMA', r'anon_inode:dmabuf'),
  ]),
  MmapCategory('Discounted tracing overhead',
               r'\[discounted tracing overhead\]')
])


# Map long descriptive attribute names, as understood by MemoryBucket.GetValue,
# to the short keys used by events in raw json traces.
BUCKET_ATTRS = {
  'proportional_resident': 'pss',
  'private_dirty_resident': 'pd',
  'private_clean_resident': 'pc',
  'shared_dirty_resident': 'sd',
  'shared_clean_resident': 'sc',
  'swapped': 'sw'}


# Map names of summary statistics a specific value within a memory category.
STATS_SUMMARY = {
  'overall_pss': '/.proportional_resident',
  'private_dirty' : '/.private_dirty_resident',
  'java_heap': '/Android/Java runtime.proportional_resident',
  'ashmem': '/Android/Ashmem.proportional_resident',
  'native_heap': '/Native heap.proportional_resident'}


class MemoryBucket(object):
  """Simple object to hold and aggregate memory values."""
  def __init__(self):
    self._bucket = dict.fromkeys(BUCKET_ATTRS.iterkeys(), 0)

  def __repr__(self):
    values = ', '.join('%s=%d' % (src_key, self._bucket[dst_key])
                       for dst_key, src_key
                       in sorted(BUCKET_ATTRS.iteritems()))
    return '%s[%s]' % (type(self).__name__, values)

  def AddRegion(self, byte_stats):
    for dst_key, src_key in BUCKET_ATTRS.iteritems():
      self._bucket[dst_key] += int(byte_stats.get(src_key, '0'), 16)

  def GetValue(self, name):
    return self._bucket[name]


class ProcessMemoryDump(object):
  """Object to classify and hold memory used by a single process.

  Properties:
    dump_id: A string to identifiy processes from the same global dump.
    pid: An integer with the process id.
    start_offset_ms: Time in ms when this dump was taken, typically represented
        as an offset since the start of the global dump.
    has_mmaps: True if the memory dump has mmaps information. If False then
        GetStatsSummary will report all zeros.
  """
  def __init__(self, event):
    assert event['ph'] == 'v'

    self.dump_id = event['id']
    self.pid = event['pid']
    self.start_offset_ms = event['ts'] / 1000.0
    self._buckets = {}
    try:
      vm_regions = event['args']['dumps']['process_mmaps']['vm_regions']
    except KeyError:
      vm_regions = []
    self.has_mmaps = bool(vm_regions)
    for vm_region in vm_regions:
      self._AddRegion(vm_region)

  def _AddRegion(self, vm_region):
    path = ''
    category = ROOT_CATEGORY
    while category:
      path = posixpath.join(path, category.name)
      self.GetMemoryBucket(path).AddRegion(vm_region['bs'])
      mapped_file = vm_region['mf']
      category = category.GetMatchingChild(mapped_file)

  def __repr__(self):
    values = ['pid=%d' % self.pid]
    for key, value in sorted(self.GetStatsSummary().iteritems()):
      values.append('%s=%d' % (key, value))
    values = ', '.join(values)
    return '%s[%s]' % (type(self).__name__, values)

  def GetMemoryBucket(self, path):
    """Return the MemoryBucket associated with a category path.

    An empty bucket will be created if the path does not already exist.

    path: A string with path in the classification tree, e.g.
        '/Android/Java runtime/Cache'. Note: no trailing slash, except for
        the root path '/'.
    """
    if not path in self._buckets:
      self._buckets[path] = MemoryBucket()
    return self._buckets[path]

  def GetMemoryValue(self, value_path):
    """Return a specific value from within a MemoryBucket.

    value_path: A string composed of a path in the classification tree,
        followed by a '.', followed by a specific bucket value, e.g.
        '/Android/Java runtime/Cache.private_dirty_resident'.
    """
    path, name = value_path.rsplit('.', 1)
    return self.GetMemoryBucket(path).GetValue(name)

  def GetStatsSummary(self):
    """Get a summary of the memory usage for this process."""
    return {key: self.GetMemoryValue(value_path)
            for key, value_path in STATS_SUMMARY.iteritems()}


class MemoryDumpEvent(timeline_event.TimelineEvent):
  """Object to hold a global dump, a collection of individual process dumps.

  It's a subclass of telemetry's TimelineEvent, so it can be included in
  the stream of events yielded by timeline.model objects. A MemoryDumpEvent
  aggregates dumps for all processes carrying the same dump id.

  Args:
    events: A sequence of individual memory dump events for each process.
        All must share the same global dump id.

  Attributes:
    dump_id: A string identifying this dump.
    process_dumps: A list of ProcessMemoryDump objects with the same dump_id.
    has_mmaps: True if the memory dump has mmaps information. If False then
        GetStatsSummary will report all zeros.
  """
  def __init__(self, events):
    assert events
    self.process_dumps = [ProcessMemoryDump(event) for event in events]

    # All process dump events should have the same dump id.
    dump_ids = set(dump.dump_id for dump in self.process_dumps)
    assert len(dump_ids) == 1
    self.dump_id = dump_ids.pop()

    # We should have exactly one process dump for each pid.
    all_pids = set(dump.pid for dump in self.process_dumps)
    assert len(self.process_dumps) == len(all_pids)

    # Either all processes have mmaps or none of them do.
    has_mmaps = set(dump.has_mmaps for dump in self.process_dumps)
    assert len(has_mmaps) == 1
    self.has_mmaps = has_mmaps.pop()

    # Sort individual dumps and offset them w.r.t. the start of the global dump.
    self.process_dumps.sort(key=lambda dump: dump.start_offset_ms)
    start = self.process_dumps[0].start_offset_ms
    for dump in self.process_dumps:
      dump.start_offset_ms -= start

    # The duration of the event is the time difference between first and the
    # last process dumps contained.
    duration = self.process_dumps[-1].start_offset_ms

    super(MemoryDumpEvent, self).__init__(
        'memory-infra', 'memory_dump', start, duration)

  def __repr__(self):
    values = ['id=%s' % self.dump_id]
    for key, value in sorted(self.GetStatsSummary().iteritems()):
      values.append('%s=%d' % (key, value))
    values = ', '.join(values)
    return '%s[%s]' % (type(self).__name__, values)

  def GetStatsSummary(self):
    """Get a summary of the memory usage for this dump."""
    summary = dict.fromkeys(STATS_SUMMARY.iterkeys(), 0)
    for dump in self.process_dumps:
      for key, value in dump.GetStatsSummary().iteritems():
        summary[key] += value
    return summary
