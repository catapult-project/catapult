# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import memory_dump_event


def TestDumpEvent(dump_id='123456ABCDEF', pid=1234, start=0, mmaps=None,
                  allocators=None):
  def vm_region(mapped_file, byte_stats):
    return {
        'mf': mapped_file,
        'bs': {k: hex(v) for k, v in byte_stats.iteritems()}}

  def attrs(sizes):
    return {'attrs': {k: {'value': hex(v)} for k, v in sizes.iteritems()}}

  if allocators is None:
    allocators = {}

  event = {'ph': 'v', 'id': dump_id, 'pid': pid, 'ts': start * 1000,
           'args': {'dumps': {'allocators': {
               name: attrs(sizes) for name, sizes in allocators.iteritems()}}}}
  if mmaps:
    event['args']['dumps']['process_mmaps'] = {
        'vm_regions': [vm_region(mapped_file, byte_stats)
                       for mapped_file, byte_stats in mmaps.iteritems()]}
  return event


class ProcessMemoryDumpUnitTest(unittest.TestCase):
  def testProcessMemoryDump_categories(self):
    ALL = [2 ** x for x in range(8)]
    (JAVA_SPACES, JAVA_CACHE, ASHMEM, NATIVE_1, NATIVE_2,
     STACK, FILES_APK, DEVICE_GPU) = ALL

    memory_dump = memory_dump_event.ProcessMemoryDump(TestDumpEvent(mmaps={
      '/dev/ashmem/dalvik-space-foo': {'pss': JAVA_SPACES},
      '/dev/ashmem/dalvik-jit-code-cache': {'pss': JAVA_CACHE},
      '/dev/ashmem/other-random-stuff': {'pss': ASHMEM},
      '[heap] bar': {'pss': NATIVE_1},
      '': {'pss': NATIVE_2},
      '[stack thingy]': {'pss': STACK},
      'my_little_app.apk': {'pss': FILES_APK},
      '/dev/mali': {'pss': DEVICE_GPU},
    }))

    EXPECTED = {
      '/': sum(ALL),
      '/Android/Java runtime': JAVA_SPACES + JAVA_CACHE,
      '/Android/Ashmem': ASHMEM,
      '/Android': JAVA_SPACES + JAVA_CACHE + ASHMEM,
      '/Native heap': NATIVE_1 + NATIVE_2,
      '/Stack': STACK,
      '/Files/apk': FILES_APK,
      '/Devices': DEVICE_GPU}

    self.assertTrue(memory_dump.has_mmaps)
    for path, value in EXPECTED.iteritems():
      self.assertEquals(value,
                        memory_dump.GetMemoryBucket(path).GetValue(
                            'proportional_resident'))


class MemoryDumpEventUnitTest(unittest.TestCase):
  def testDumpEventsTiming(self):
    memory_dump = memory_dump_event.MemoryDumpEvent([
        TestDumpEvent(pid=3, start=8),
        TestDumpEvent(pid=1, start=4),
        TestDumpEvent(pid=2, start=13),
        TestDumpEvent(pid=4, start=7)])

    self.assertFalse(memory_dump.has_mmaps)
    self.assertEquals(4,
                      len(memory_dump.process_dumps))
    self.assertAlmostEquals(4.0,
                            memory_dump.start)
    self.assertAlmostEquals(13.0,
                            memory_dump.end)
    self.assertAlmostEquals(9.0,
                            memory_dump.duration)

  def testGetStatsSummary(self):
    ALL = [2 ** x for x in range(7)]
    (JAVA_HEAP_1, JAVA_HEAP_2, ASHMEM_1, ASHMEM_2, NATIVE,
     DIRTY_1, DIRTY_2) = ALL

    memory_dump = memory_dump_event.MemoryDumpEvent([
        TestDumpEvent(pid=1, mmaps={
            '/dev/ashmem/dalvik-alloc space': {'pss': JAVA_HEAP_1}}),
        TestDumpEvent(pid=2, mmaps={
            '/dev/ashmem/other-ashmem': {'pss': ASHMEM_1, 'pd': DIRTY_1}}),
        TestDumpEvent(pid=3, mmaps={
            '[heap] native': {'pss': NATIVE, 'pd': DIRTY_2},
            '/dev/ashmem/dalvik-zygote space': {'pss': JAVA_HEAP_2}}),
        TestDumpEvent(pid=4, mmaps={
            '/dev/ashmem/other-ashmem': {'pss': ASHMEM_2}})])

    self.assertTrue(memory_dump.has_mmaps)
    self.assertEquals({'overall_pss': sum(ALL[:5]),
                       'private_dirty': DIRTY_1 + DIRTY_2,
                       'java_heap': JAVA_HEAP_1 + JAVA_HEAP_2,
                       'ashmem': ASHMEM_1 + ASHMEM_2,
                       'native_heap': NATIVE},
                      memory_dump.GetStatsSummary())

  def testGetStatsSummaryDiscountsTracing(self):
    ALL = [2 ** x for x in range(5)]
    (HEAP, DIRTY, MALLOC, TRACING_1, TRACING_2) = ALL

    memory_dump = memory_dump_event.MemoryDumpEvent([
        TestDumpEvent(
            mmaps={'/dev/ashmem/libc malloc': {'pss': HEAP + TRACING_2,
                                               'pd': DIRTY + TRACING_2}},
            allocators={
                'tracing': {'size': TRACING_1, 'resident_size': TRACING_2},
                'malloc': {'size': MALLOC + TRACING_1}})])

    self.assertEquals({'overall_pss': HEAP,
                       'private_dirty': DIRTY,
                       'java_heap': 0,
                       'ashmem': 0,
                       'native_heap': HEAP},
                      memory_dump.GetStatsSummary())
    self.assertEquals({'tracing': TRACING_1,
                       'malloc': MALLOC},
                      memory_dump.GetAllocatorStats())
