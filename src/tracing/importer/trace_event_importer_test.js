// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.trace_event_importer');

base.unittest.testSuite('tracing.importer.trace_event_importer', function() {
  var findSliceNamed = tracing.test_utils.findSliceNamed;

  test('canImportEmpty', function() {
    self.assertFalse(tracing.importer.TraceEventImporter.canImport([]));
    self.assertFalse(tracing.importer.TraceEventImporter.canImport(''));
  });

  test('basicSingleThreadNonnestedParsing', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'},
      {name: 'b', args: {}, pid: 52, ts: 629, cat: 'bar', tid: 53, ph: 'B'},
      {name: 'b', args: {}, pid: 52, ts: 631, cat: 'bar', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
    var p = m.processes[52];
    assertNotUndefined(p);

    assertEquals(1, p.numThreads);
    var t = p.threads[53];
    assertNotUndefined(t);
    assertEquals(2, t.sliceGroup.length);
    assertEquals(53, t.tid);
    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertAlmostEquals((560 - 520) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);

    slice = t.sliceGroup.slices[1];
    assertEquals('b', slice.title);
    assertEquals('bar', slice.category);
    assertAlmostEquals((629 - 520) / 1000, slice.start);
    assertAlmostEquals((631 - 629) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);
  });

  test('argumentDupeCreatesNonFailingImportError', function() {
    var events = [
      {name: 'a',
        args: {'x': 1},
        pid: 1,
        ts: 520,
        cat: 'foo',
        tid: 1,
        ph: 'B'},
      {name: 'a',
        args: {'x': 2},
        pid: 1,
        ts: 560,
        cat: 'foo',
        tid: 1,
        ph: 'E'}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[1].threads[1];
    var sA = findSliceNamed(t.sliceGroup, 'a');

    assertEquals(2, sA.args.x);
    assertEquals(m.importErrors.length, 1);
  });

  test('categoryBeginEndMismatchPrefersBegin', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'bar', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
    var p = m.processes[52];
    assertNotUndefined(p);

    assertEquals(1, p.numThreads);
    var t = p.threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(53, t.tid);
    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
  });

  test('nestedParsing', function() {
    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 2, cat: 'bar', tid: 1, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 3, cat: 'bar', tid: 1, ph: 'E'},
      {name: 'a', args: {}, pid: 1, ts: 4, cat: 'foo', tid: 1, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events, false);
    var t = m.processes[1].threads[1];

    var sA = findSliceNamed(t.sliceGroup, 'a');
    var sB = findSliceNamed(t.sliceGroup, 'b');

    assertEquals('a', sA.title);
    assertEquals('foo', sA.category);
    assertEquals(0.001, sA.start);
    assertEquals(0.003, sA.duration);

    assertEquals('b', sB.title);
    assertEquals('bar', sB.category);
    assertEquals(0.002, sB.start);
    assertEquals(0.001, sB.duration);
  });

  test('autoclosing', function() {
    var events = [
      // Slice that doesn't finish.
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},

      // Slice that does finish to give an 'end time' to make autoclosing work.
      {name: 'b', args: {}, pid: 1, ts: 1, cat: 'bar', tid: 2, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 2, cat: 'bar', tid: 2, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var t = p.threads[1];
    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertTrue(slice.didNotFinish);
    assertEquals(0, slice.start);
    assertEquals((2 - 1) / 1000, slice.duration);
  });

  test('autoclosingLoneBegin', function() {
    var events = [
      // Slice that doesn't finish.
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var t = p.threads[1];
    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertTrue(slice.didNotFinish);
    assertEquals(0, slice.start);
    assertEquals(0, slice.duration);
  });

  test('autoclosingWithSubTasks', function() {
    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'b1', args: {}, pid: 1, ts: 2, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'b1', args: {}, pid: 1, ts: 3, cat: 'foo', tid: 1, ph: 'E'},
      {name: 'b2', args: {}, pid: 1, ts: 3, cat: 'foo', tid: 1, ph: 'B'}
    ];
    var m = new tracing.TraceModel(events, false);
    var t = m.processes[1].threads[1];

    var sA = findSliceNamed(t.sliceGroup, 'a');
    var sB1 = findSliceNamed(t.sliceGroup, 'b1');
    var sB2 = findSliceNamed(t.sliceGroup, 'b2');

    assertEquals(0.003, sA.end);
    assertEquals(0.003, sB1.end);
    assertEquals(0.003, sB2.end);
  });

  test('autoclosingWithEventsOutsideBounds', function() {
    var events = [
      // Slice that begins before min and ends after max of the other threads.
      {name: 'a', args: {}, pid: 1, ts: 0, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 3, cat: 'foo', tid: 1, ph: 'B'},

      // Slice that does finish to give an 'end time' to establish a basis
      {name: 'c', args: {}, pid: 1, ts: 1, cat: 'bar', tid: 2, ph: 'B'},
      {name: 'c', args: {}, pid: 1, ts: 2, cat: 'bar', tid: 2, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events, false);
    var p = m.processes[1];
    var t = p.threads[1];
    assertEquals(2, t.sliceGroup.length);

    var slice = findSliceNamed(t.sliceGroup, 'a');
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertEquals(0.003, slice.duration);

    var t2 = p.threads[2];
    var slice2 = findSliceNamed(t2.sliceGroup, 'c');
    assertEquals('c', slice2.title);
    assertEquals('bar', slice2.category);
    assertEquals(0.001, slice2.start);
    assertEquals(0.001, slice2.duration);

    assertEquals(0.000, m.bounds.min);
    assertEquals(0.003, m.bounds.max);
  });

  test('nestedAutoclosing', function() {
    var events = [
      // Tasks that don't finish.
      {name: 'a1', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'a2', args: {}, pid: 1, ts: 1.5, cat: 'foo', tid: 1, ph: 'B'},

      // Slice that does finish to give an 'end time' to make autoclosing work.
      {name: 'b', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 2, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 2, cat: 'foo', tid: 2, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events, false);
    var t1 = m.processes[1].threads[1];
    var t2 = m.processes[1].threads[2];

    var sA1 = findSliceNamed(t1.sliceGroup, 'a1');
    var sA2 = findSliceNamed(t1.sliceGroup, 'a2');
    var sB = findSliceNamed(t2.sliceGroup, 'b');

    assertEquals(0.002, sA1.end);
    assertEquals(0.002, sA2.end);
  });

  test('taskColoring', function() {
    // The test below depends on hashing of 'a' != 'b'. Fail early if that
    // assumption is incorrect.
    assertNotEquals(tracing.getStringHash('a'), tracing.getStringHash('b'));

    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'a', args: {}, pid: 1, ts: 2, cat: 'foo', tid: 1, ph: 'E'},
      {name: 'b', args: {}, pid: 1, ts: 3, cat: 'bar', tid: 1, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 4, cat: 'bar', tid: 1, ph: 'E'},
      {name: 'a', args: {}, pid: 1, ts: 5, cat: 'baz', tid: 1, ph: 'B'},
      {name: 'a', args: {}, pid: 1, ts: 6, cat: 'baz', tid: 1, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var t = p.threads[1];
    var a1 = t.sliceGroup.slices[0];
    assertEquals('a', a1.title);
    assertEquals('foo', a1.category);
    var b = t.sliceGroup.slices[1];
    assertEquals('b', b.title);
    assertEquals('bar', b.category);
    assertNotEquals(a1.colorId, b.colorId);
    var a2 = t.sliceGroup.slices[2];
    assertEquals('a', a2.title);
    assertEquals('baz', a2.category);
    assertEquals(a1.colorId, a2.colorId);
  });

  test('multipleThreadParsing', function() {
    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'a', args: {}, pid: 1, ts: 2, cat: 'foo', tid: 1, ph: 'E'},
      {name: 'b', args: {}, pid: 1, ts: 3, cat: 'bar', tid: 2, ph: 'B'},
      {name: 'b', args: {}, pid: 1, ts: 4, cat: 'bar', tid: 2, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
    var p = m.processes[1];
    assertNotUndefined(p);

    assertEquals(2, p.numThreads);

    // Check thread 1.
    var t = p.threads[1];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(1, t.tid);

    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertEquals((2 - 1) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);

    // Check thread 2.
    var t = p.threads[2];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(2, t.tid);

    slice = t.sliceGroup.slices[0];
    assertEquals('b', slice.title);
    assertEquals('bar', slice.category);
    assertEquals((3 - 1) / 1000, slice.start);
    assertEquals((4 - 3) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);
  });

  test('multiplePidParsing', function() {
    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'a', args: {}, pid: 1, ts: 2, cat: 'foo', tid: 1, ph: 'E'},
      {name: 'b', args: {}, pid: 2, ts: 3, cat: 'bar', tid: 2, ph: 'B'},
      {name: 'b', args: {}, pid: 2, ts: 4, cat: 'bar', tid: 2, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events);
    assertEquals(2, m.numProcesses);
    var p = m.processes[1];
    assertNotUndefined(p);

    assertEquals(1, p.numThreads);

    // Check process 1 thread 1.
    var t = p.threads[1];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(1, t.tid);

    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertEquals((2 - 1) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);

    // Check process 2 thread 2.
    var p = m.processes[2];
    assertNotUndefined(p);
    assertEquals(1, p.numThreads);
    var t = p.threads[2];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(2, t.tid);

    slice = t.sliceGroup.slices[0];
    assertEquals('b', slice.title);
    assertEquals('bar', slice.category);
    assertEquals((3 - 1) / 1000, slice.start);
    assertEquals((4 - 3) / 1000, slice.duration);
    assertEquals(0, slice.subSlices.length);

    // Check getAllThreads.
    assertArrayEquals([m.processes[1].threads[1], m.processes[2].threads[2]],
                      m.getAllThreads());
  });

  // Process names.
  test('processNames', function() {
    var events = [
      {name: 'process_name', args: {name: 'SomeProcessName'},
        pid: 1, ts: 0, tid: 1, ph: 'M'},
      {name: 'process_name', args: {name: 'SomeProcessName'},
        pid: 2, ts: 0, tid: 1, ph: 'M'}
    ];
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);
    assertEquals('SomeProcessName', m.processes[1].name);
  });

  // Process labels.
  test('processLabels', function() {
    var events = [
      {name: 'process_labels', args: {labels: 'foo,bar'},
        pid: 1, ts: 0, tid: 1, ph: 'M'},
      {name: 'process_labels', args: {labels: 'baz'},
        pid: 2, ts: 0, tid: 1, ph: 'M'}
    ];
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);
    assertArrayEquals(['foo', 'bar'], m.processes[1].labels);
    assertArrayEquals(['baz'], m.processes[2].labels);
  });

  // Process sort index.
  test('processSortIndex', function() {
    var events = [
      {name: 'process_name', args: {name: 'First'},
        pid: 2, ts: 0, tid: 1, ph: 'M'},
      {name: 'process_name', args: {name: 'Second'},
        pid: 2, ts: 0, tid: 1, ph: 'M'},
      {name: 'process_sort_index', args: {sort_index: 1},
        pid: 1, ts: 0, tid: 1, ph: 'M'}
    ];
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);

    // By name, p1 is before p2. But, its sort index overrides that.
    assertTrue(m.processes[1].compareTo(m.processes[2]) > 0);
  });

  // Thread names.
  test('threadNames', function() {
    var events = [
      {name: 'thread_name', args: {name: 'Thread 1'},
        pid: 1, ts: 0, tid: 1, ph: 'M'},
      {name: 'thread_name', args: {name: 'Thread 2'},
        pid: 2, ts: 0, tid: 2, ph: 'M'}
    ];
    var m = new tracing.TraceModel(events);
    m.importTraces([events], false, false);
    assertEquals('Thread 1', m.processes[1].threads[1].name);
    assertEquals('Thread 2', m.processes[2].threads[2].name);
  });

  // Thread sort index.
  test('threadSortIndex', function() {
    var events = [
      {name: 'thread_name', args: {name: 'Thread 1'},
        pid: 1, ts: 0, tid: 1, ph: 'M'},
      {name: 'thread_name', args: {name: 'Thread 2'},
        pid: 1, ts: 0, tid: 2, ph: 'M'},
      {name: 'thread_sort_index', args: {sort_index: 1},
        pid: 1, ts: 0, tid: 1, ph: 'M'}
    ];
    var m = new tracing.TraceModel();
    m.importTraces([events], false, false);

    // By name, t1 is before t2. But, its sort index overrides that.
    var t1 = m.processes[1].threads[1];
    var t2 = m.processes[1].threads[2];
    assertTrue(t1.compareTo(t2) > 0);
  });

  test('parsingWhenEndComesFirst', function() {
    var events = [
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'E'},
      {name: 'a', args: {}, pid: 1, ts: 4, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'a', args: {}, pid: 1, ts: 5, cat: 'foo', tid: 1, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events, false);
    var p = m.processes[1];
    var t = p.threads[1];
    assertEquals(1, t.sliceGroup.length);
    assertEquals('a', t.sliceGroup.slices[0].title);
    assertEquals('foo', t.sliceGroup.slices[0].category);
    assertEquals(0.004, t.sliceGroup.slices[0].start);
    assertEquals(0.001, t.sliceGroup.slices[0].duration);
    assertEquals(1, m.importErrors.length);
  });

  test('immediateParsing', function() {
    var events = [
      // Need to include immediates inside a task so the timeline
      // recentering/zeroing doesn't clobber their timestamp.
      {name: 'a', args: {}, pid: 1, ts: 1, cat: 'foo', tid: 1, ph: 'B'},
      {name: 'immediate', args: {}, pid: 1, ts: 2, cat: 'bar', tid: 1, ph: 'I'},
      {name: 'slower', args: {}, pid: 1, ts: 4, cat: 'baz', tid: 1, ph: 'i'},
      {name: 'a', args: {}, pid: 1, ts: 4, cat: 'foo', tid: 1, ph: 'E'}
    ];
    var m = new tracing.TraceModel(events, false);
    var p = m.processes[1];
    var t = p.threads[1];

    assertEquals(3, t.sliceGroup.length);
    assertEquals(0.002, t.sliceGroup.slices[0].start);
    assertEquals(0, t.sliceGroup.slices[0].duration);
    assertEquals(0.004, t.sliceGroup.slices[1].start);
    assertEquals(0.001, t.sliceGroup.slices[2].start);
    assertEquals(0.003, t.sliceGroup.slices[2].duration);

    var slice = findSliceNamed(t.sliceGroup, 'a');
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0.003, slice.duration);

    var immed = findSliceNamed(t.sliceGroup, 'immediate');
    assertEquals('immediate', immed.title);
    assertEquals('bar', immed.category);
    assertEquals(0.002, immed.start);
    assertEquals(0, immed.duration);

    var slower = findSliceNamed(t.sliceGroup, 'slower');
    assertEquals('slower', slower.title);
    assertEquals('baz', slower.category);
    assertEquals(0.004, slower.start);
    assertEquals(0, slower.duration);
  });

  test('simpleCounter', function() {
    var events = [
      {name: 'ctr', args: {'value': 0}, pid: 1, ts: 0, cat: 'foo', tid: 1,
        ph: 'C'},
      {name: 'ctr', args: {'value': 10}, pid: 1, ts: 10, cat: 'foo', tid: 1,
        ph: 'C'},
      {name: 'ctr', args: {'value': 0}, pid: 1, ts: 20, cat: 'foo', tid: 1,
        ph: 'C'}

    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var ctr = m.processes[1].counters['foo.ctr'];

    assertEquals('ctr', ctr.name);
    assertEquals('foo', ctr.category);
    assertEquals(3, ctr.numSamples);
    assertEquals(1, ctr.numSeries);

    assertEquals('value', ctr.series[0].name);
    assertEquals(tracing.getStringColorId('ctr.value'), ctr.series[0].color);

    assertArrayEquals([0, 0.01, 0.02], ctr.timestamps);

    var samples = [];
    ctr.series[0].samples.forEach(function(sample) {
      samples.push(sample.value);
    });
    assertArrayEquals([0, 10, 0], samples);

    assertArrayEquals([0, 10, 0], ctr.totals);
    assertEquals(10, ctr.maxTotal);
  });

  test('instanceCounter', function() {
    var events = [
      {name: 'ctr', args: {'value': 0}, pid: 1, ts: 0, cat: 'foo', tid: 1,
        ph: 'C', id: 0},
      {name: 'ctr', args: {'value': 10}, pid: 1, ts: 10, cat: 'foo', tid: 1,
        ph: 'C', id: 0},
      {name: 'ctr', args: {'value': 10}, pid: 1, ts: 10, cat: 'foo', tid: 1,
        ph: 'C', id: 1},
      {name: 'ctr', args: {'value': 20}, pid: 1, ts: 15, cat: 'foo', tid: 1,
        ph: 'C', id: 1},
      {name: 'ctr', args: {'value': 30}, pid: 1, ts: 18, cat: 'foo', tid: 1,
        ph: 'C', id: 1},
      {name: 'ctr', args: {'value': 40}, pid: 1, ts: 20, cat: 'bar', tid: 1,
        ph: 'C', id: 2}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var ctr = m.processes[1].counters['foo.ctr[0]'];
    assertEquals('ctr[0]', ctr.name);
    assertEquals('foo', ctr.category);
    assertEquals(2, ctr.numSamples);
    assertEquals(1, ctr.numSeries);

    assertArrayEquals([0, 0.01], ctr.timestamps);
    var samples = [];
    ctr.series[0].samples.forEach(function(sample) {
      samples.push(sample.value);
    });
    assertArrayEquals([0, 10], samples);

    ctr = m.processes[1].counters['foo.ctr[1]'];
    assertEquals('ctr[1]', ctr.name);
    assertEquals('foo', ctr.category);
    assertEquals(3, ctr.numSamples);
    assertEquals(1, ctr.numSeries);
    assertArrayEquals([0.01, 0.015, 0.018], ctr.timestamps);

    samples = [];
    ctr.series[0].samples.forEach(function(sample) {
      samples.push(sample.value);
    });
    assertArrayEquals([10, 20, 30], samples);

    ctr = m.processes[1].counters['bar.ctr[2]'];
    assertEquals('ctr[2]', ctr.name);
    assertEquals('bar', ctr.category);
    assertEquals(1, ctr.numSamples);
    assertEquals(1, ctr.numSeries);
    assertArrayEquals([0.02], ctr.timestamps);
    var samples = [];
    ctr.series[0].samples.forEach(function(sample) {
      samples.push(sample.value);
    });
    assertArrayEquals([40], samples);
  });

  test('multiCounterUpdateBounds', function() {
    var ctr = new tracing.trace_model.Counter(undefined, 'testBasicCounter',
        '', 'testBasicCounter');
    var value1Series = new tracing.trace_model.CounterSeries(
        'value1', 'testBasicCounter.value1');
    var value2Series = new tracing.trace_model.CounterSeries(
        'value2', 'testBasicCounter.value2');
    ctr.addSeries(value1Series);
    ctr.addSeries(value2Series);

    value1Series.addSample(0, 0);
    value1Series.addSample(1, 1);
    value1Series.addSample(2, 1);
    value1Series.addSample(3, 2);
    value1Series.addSample(4, 3);
    value1Series.addSample(5, 1);
    value1Series.addSample(6, 3);
    value1Series.addSample(7, 3.1);

    value2Series.addSample(0, 0);
    value2Series.addSample(1, 0);
    value2Series.addSample(2, 1);
    value2Series.addSample(3, 1.1);
    value2Series.addSample(4, 0);
    value2Series.addSample(5, 7);
    value2Series.addSample(6, 0);
    value2Series.addSample(7, 0.5);

    ctr.updateBounds();

    assertEquals(0, ctr.bounds.min);
    assertEquals(7, ctr.bounds.max);
    assertEquals(8, ctr.maxTotal);
    assertArrayEquals([0, 0,
                       1, 1,
                       1, 2,
                       2, 3.1,
                       3, 3,
                       1, 8,
                       3, 3,
                       3.1, 3.6], ctr.totals);
  });

  test('multiCounter', function() {
    var events = [
      {name: 'ctr', args: {'value1': 0, 'value2': 7}, pid: 1, ts: 0, cat: 'foo', tid: 1, ph: 'C'}, // @suppress longLineCheck
      {name: 'ctr', args: {'value1': 10, 'value2': 4}, pid: 1, ts: 10, cat: 'foo', tid: 1, ph: 'C'}, // @suppress longLineCheck
      {name: 'ctr', args: {'value1': 0, 'value2': 1 }, pid: 1, ts: 20, cat: 'foo', tid: 1, ph: 'C'} // @suppress longLineCheck
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[1];
    var ctr = m.processes[1].counters['foo.ctr'];
    assertEquals('ctr', ctr.name);

    assertEquals('ctr', ctr.name);
    assertEquals('foo', ctr.category);
    assertEquals(3, ctr.numSamples);
    assertEquals(2, ctr.numSeries);

    assertEquals('value1', ctr.series[0].name);
    assertEquals('value2', ctr.series[1].name);
    assertEquals(tracing.getStringColorId('ctr.value1'), ctr.series[0].color);
    assertEquals(tracing.getStringColorId('ctr.value2'), ctr.series[1].color);

    assertArrayEquals([0, 0.01, 0.02], ctr.timestamps);
    var samples = [];
    ctr.series[0].samples.forEach(function(sample) {
      samples.push(sample.value);
    });
    assertArrayEquals([0, 10, 0], samples);

    var samples1 = [];
    ctr.series[1].samples.forEach(function(sample) {
      samples1.push(sample.value);
    });
    assertArrayEquals([7, 4, 1], samples1);
    assertArrayEquals([0, 7,
                       10, 14,
                       0, 1], ctr.totals);
    assertEquals(14, ctr.maxTotal);
  });

  test('importObjectInsteadOfArray', function() {
    var events = { traceEvents: [
      {name: 'a', args: {}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ] };

    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
  });

  test('importString', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(JSON.stringify(events));
    assertEquals(1, m.numProcesses);
  });

  test('importStringWithTrailingNewLine', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(JSON.stringify(events) + '\n');
    assertEquals(1, m.numProcesses);
  });

  test('importStringWithMissingCloseSquareBracket', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var tmp = JSON.stringify(events);
    assertEquals(']', tmp[tmp.length - 1]);

    // Drop off the trailing ]
    var dropped = tmp.substring(0, tmp.length - 1);
    var m = new tracing.TraceModel(dropped);
    assertEquals(1, m.numProcesses);
  });

  test('importStringWithEndingCommaButMissingCloseSquareBracket', function() {
    var lines = [
      '[',
      '{"name": "a", "args": {}, "pid": 52, "ts": 524, "cat": "foo", "tid": 53, "ph": "B"},', // @suppress longLineCheck
      '{"name": "a", "args": {}, "pid": 52, "ts": 560, "cat": "foo", "tid": 53, "ph": "E"},' // @suppress longLineCheck
    ];
    var text = lines.join('\n');

    var m = new tracing.TraceModel(text);
    assertEquals(1, m.numProcesses);
    assertEquals(1, m.processes[52].threads[53].sliceGroup.length);
  });

  test('importStringWithMissingCloseSquareBracketAndNewline', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var tmp = JSON.stringify(events);
    assertEquals(']', tmp[tmp.length - 1]);

    // Drop off the trailing ] and add a newline
    var dropped = tmp.substring(0, tmp.length - 1);
    var m = new tracing.TraceModel(dropped + '\n');
    assertEquals(1, m.numProcesses);
  });

  test('ImportStringEndingCommaButMissingCloseSquareBracketCRLF', function() {
    var lines = [
      '[',
      '{"name": "a", "args": {}, "pid": 52, "ts": 524, "cat": "foo", "tid": 53, "ph": "B"},', // @suppress longLineCheck
      '{"name": "a", "args": {}, "pid": 52, "ts": 560, "cat": "foo", "tid": 53, "ph": "E"},' // @suppress longLineCheck
    ];
    var text = lines.join('\r\n');

    var m = new tracing.TraceModel(text);
    assertEquals(1, m.numProcesses);
    assertEquals(1, m.processes[52].threads[53].sliceGroup.length);
  });

  test('importOldFormat', function() {
    var lines = [
      '[',
      '{"cat":"a","pid":9,"tid":8,"ts":194,"ph":"E","name":"I","args":{}},',
      '{"cat":"b","pid":9,"tid":8,"ts":194,"ph":"B","name":"I","args":{}}',
      ']'
    ];
    var text = lines.join('\n');
    var m = new tracing.TraceModel(text);
    assertEquals(1, m.numProcesses);
    assertEquals(1, m.processes[9].threads[8].sliceGroup.length);
  });

  test('startFinishOneSliceOneThread', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'a', args: {}, pid: 52, ts: 560, cat: 'cat', tid: 53,
        ph: 'F', id: 72},
      {name: 'a', pid: 52, ts: 524, cat: 'cat', tid: 53,
        ph: 'S', id: 72, args: {'foo': 'bar'}}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.asyncSliceGroup.slices.length);
    assertEquals('a', t.asyncSliceGroup.slices[0].title);
    assertEquals('cat', t.asyncSliceGroup.slices[0].category);
    assertEquals(72, t.asyncSliceGroup.slices[0].id);
    assertEquals('bar', t.asyncSliceGroup.slices[0].args.foo);
    assertEquals(0, t.asyncSliceGroup.slices[0].start);
    assertAlmostEquals((60 - 24) / 1000, t.asyncSliceGroup.slices[0].duration);
    assertEquals(t, t.asyncSliceGroup.slices[0].startThread);
    assertEquals(t, t.asyncSliceGroup.slices[0].endThread);
  });

  test('endArgsAddedToSlice', function() {
    var events = [
      {name: 'a', args: {x: 1}, pid: 52, ts: 520, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'a', args: {y: 2}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
    var p = m.processes[52];
    assertNotUndefined(p);

    assertEquals(1, p.numThreads);
    var t = p.threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.sliceGroup.length);
    assertEquals(53, t.tid);
    var slice = t.sliceGroup.slices[0];
    assertEquals('a', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertEquals(0, slice.subSlices.length);
    assertEquals(1, slice.args['x']);
    assertEquals(2, slice.args['y']);
  });

  test('endArgOverrwritesOriginalArgValueIfDuplicated', function() {
    var events = [
      {name: 'b', args: {z: 3}, pid: 52, ts: 629, cat: 'foo', tid: 53, ph: 'B'},
      {name: 'b', args: {z: 4}, pid: 52, ts: 631, cat: 'foo', tid: 53, ph: 'E'}
    ];

    var m = new tracing.TraceModel(events);
    assertEquals(1, m.numProcesses);
    var p = m.processes[52];
    assertNotUndefined(p);

    assertEquals(1, p.numThreads);
    var t = p.threads[53];
    assertNotUndefined(t);
    var slice = t.sliceGroup.slices[0];
    assertEquals('b', slice.title);
    assertEquals('foo', slice.category);
    assertEquals(0, slice.start);
    assertEquals(0, slice.subSlices.length);
    assertEquals(4, slice.args['z']);
  });

  test('asyncEndArgsAddedToSlice', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'c', args: {y: 2}, pid: 52, ts: 560, cat: 'foo', tid: 53,
        ph: 'F', id: 72},
      {name: 'c', args: {x: 1}, pid: 52, ts: 524, cat: 'foo', tid: 53,
        ph: 'S', id: 72}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.asyncSliceGroup.slices.length);
    var parentSlice = t.asyncSliceGroup.slices[0];
    assertEquals('c', parentSlice.title);
    assertEquals('foo', parentSlice.category);

    assertNotUndefined(parentSlice.subSlices);
    assertEquals(1, parentSlice.subSlices.length);
    var subSlice = parentSlice.subSlices[0];
    assertEquals(1, subSlice.args['x']);
    assertEquals(2, subSlice.args['y']);
  });

  test('asyncEndArgOverrwritesOriginalArgValueIfDuplicated', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'd', args: {z: 4}, pid: 52, ts: 560, cat: 'foo', tid: 53,
        ph: 'F', id: 72},
      {name: 'd', args: {z: 3}, pid: 52, ts: 524, cat: 'foo', tid: 53,
        ph: 'S', id: 72}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.asyncSliceGroup.slices.length);
    var parentSlice = t.asyncSliceGroup.slices[0];
    assertEquals('d', parentSlice.title);
    assertEquals('foo', parentSlice.category);

    assertNotUndefined(parentSlice.subSlices);
    assertEquals(1, parentSlice.subSlices.length);
    var subSlice = parentSlice.subSlices[0];
    assertEquals(4, subSlice.args['z']);
  });

  test('asyncStepsInOneThread', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'a', args: {z: 3}, pid: 52, ts: 560, cat: 'foo', tid: 53, ph: 'F', id: 72}, // @suppress longLineCheck
      {name: 'a', args: {step: 's1', y: 2}, pid: 52, ts: 548, cat: 'foo', tid: 53, ph: 'T', id: 72}, // @suppress longLineCheck
      {name: 'a', args: {x: 1}, pid: 52, ts: 524, cat: 'foo', tid: 53, ph: 'S', id: 72} // @suppress longLineCheck
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertNotUndefined(t);
    assertEquals(1, t.asyncSliceGroup.slices.length);
    var parentSlice = t.asyncSliceGroup.slices[0];
    assertEquals('a', parentSlice.title);
    assertEquals('foo', parentSlice.category);
    assertEquals(0, parentSlice.start);

    assertNotUndefined(parentSlice.subSlices);
    assertEquals(2, parentSlice.subSlices.length);
    var subSlice = parentSlice.subSlices[0];
    assertEquals('a', subSlice.title);
    assertEquals('foo', subSlice.category);
    assertEquals(0, subSlice.start);
    assertAlmostEquals((548 - 524) / 1000, subSlice.duration);
    assertEquals(1, subSlice.args['x']);

    var subSlice = parentSlice.subSlices[1];
    assertEquals('a:s1', subSlice.title);
    assertEquals('foo', subSlice.category);
    assertAlmostEquals((548 - 524) / 1000, subSlice.start);
    assertAlmostEquals((560 - 548) / 1000, subSlice.duration);
    assertEquals(2, subSlice.args['y']);
    assertEquals(3, subSlice.args['z']);
  });

  test('asyncStepsMissingStart', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'a', args: {z: 3}, pid: 52, ts: 560, cat: 'foo', tid: 53,
        ph: 'F', id: 72},
      {name: 'a', args: {step: 's1', y: 2}, pid: 52, ts: 548, cat: 'foo',
        tid: 53, ph: 'T', id: 72}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertUndefined(t);
  });

  test('asyncStepsMissingFinish', function() {
    var events = [
      // Time is intentionally out of order.
      {name: 'a', args: {step: 's1', y: 2}, pid: 52, ts: 548, cat: 'foo',
        tid: 53, ph: 'T', id: 72},
      {name: 'a', args: {z: 3}, pid: 52, ts: 560, cat: 'foo', tid: 53,
        ph: 'S', id: 72}
    ];

    var m = new tracing.TraceModel(events);
    var t = m.processes[52].threads[53];
    assertUndefined(t);
  });

  test('importSamples', function() {
    var events = [
      {name: 'a', args: {}, pid: 52, ts: 548, cat: 'test', tid: 53, ph: 'P'},
      {name: 'b', args: {}, pid: 52, ts: 548, cat: 'test', tid: 53, ph: 'P'},
      {name: 'c', args: {}, pid: 52, ts: 558, cat: 'test', tid: 53, ph: 'P'}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[52];
    assertNotUndefined(p);
    var t = p.threads[53];
    assertNotUndefined(t);
    assertEquals(3, t.samples_.length);
    assertEquals(0.0, t.samples_[0].start);
    assertEquals(0.0, t.samples_[1].start);
    assertApproxEquals(0.01, t.samples_[2].start);
    assertEquals('a', t.samples_[0].title);
    assertEquals('b', t.samples_[1].title);
    assertEquals('c', t.samples_[2].title);
    assertEquals(0, m.importErrors.length);
  });

  test('importSamplesMissingArgs', function() {
    var events = [
      {name: 'a', pid: 52, ts: 548, cat: 'test', tid: 53, ph: 'P'},
      {name: 'b', pid: 52, ts: 548, cat: 'test', tid: 53, ph: 'P'},
      {name: 'c', pid: 52, ts: 549, cat: 'test', tid: 53, ph: 'P'}
    ];
    var m = new tracing.TraceModel(events);
    var p = m.processes[52];
    assertNotUndefined(p);
    var t = p.threads[53];
    assertNotUndefined(t);
    assertNotUndefined(t);
    assertEquals(3, t.samples_.length);
    assertEquals(0, m.importErrors.length);
  });

  test('importSimpleObject', function() {
    var events = [
      {ts: 10000, pid: 1, tid: 1, ph: 'N', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck
      {ts: 15000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: {snapshot: 15}}, // @suppress longLineCheck
      {ts: 20000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: {snapshot: 20}}, // @suppress longLineCheck
      {ts: 50000, pid: 1, tid: 1, ph: 'D', cat: 'c', id: '0x1000', name: 'a', args: {}} // @suppress longLineCheck
    ];
    var m = new tracing.TraceModel();
    m.importTraces([events], false);
    assertEquals(10, m.bounds.min);
    assertEquals(50, m.bounds.max);
    assertEquals(0, m.importErrors.length);

    var p = m.processes[1];
    assertNotUndefined(p);

    var i10 = p.objects.getObjectInstanceAt('0x1000', 10);
    assertEquals('c', i10.category);
    assertEquals(10, i10.creationTs);
    assertEquals(50, i10.deletionTs);
    assertEquals(2, i10.snapshots.length);

    var s15 = i10.snapshots[0];
    assertEquals(15, s15.ts);
    assertEquals(15, s15.args);

    var s20 = i10.snapshots[1];
    assertEquals(20, s20.ts);
    assertEquals(20, s20.args);
  });

  test('iimportImplicitObjects', function() {
    var events = [
      {ts: 10000, pid: 1, tid: 1, ph: 'N', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck
      {ts: 15000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a',
        args: { snapshot: [
          { id: 'subObject/0x1',
            foo: 1
          }
        ]}},
      {ts: 20000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a',
        args: { snapshot: [
          { id: 'subObject/0x1',
            foo: 2
          },
          { id: 'subObject/0x2',
            foo: 1
          }
        ]}}
    ];

    var m = new tracing.TraceModel();
    m.importTraces([events], false);
    var p1 = m.processes[1];

    var iA = p1.objects.getObjectInstanceAt('0x1000', 10);
    var subObjectInstances = p1.objects.getAllInstancesByTypeName()[
        'subObject'];

    assertEquals(2, subObjectInstances.length);
    var subObject1 = p1.objects.getObjectInstanceAt('0x1', 15);
    assertEquals('subObject', subObject1.name);
    assertEquals(15, subObject1.creationTs);

    assertEquals(2, subObject1.snapshots.length);
    assertEquals(15, subObject1.snapshots[0].ts);
    assertEquals(1, subObject1.snapshots[0].args.foo);
    assertEquals(20, subObject1.snapshots[1].ts);
    assertEquals(2, subObject1.snapshots[1].args.foo);

    var subObject2 = p1.objects.getObjectInstanceAt('0x2', 20);
    assertEquals('subObject', subObject2.name);
    assertEquals(20, subObject2.creationTs);
    assertEquals(1, subObject2.snapshots.length);
    assertEquals(20, subObject2.snapshots[0].ts);
  });

  test('importIDRefs', function() {
    var events = [
      // An object with two snapshots.
      {ts: 10000, pid: 1, tid: 1, ph: 'N', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck
      {ts: 15000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: {snapshot: 15}}, // @suppress longLineCheck
      {ts: 20000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: {snapshot: 20}}, // @suppress longLineCheck
      {ts: 50000, pid: 1, tid: 1, ph: 'D', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck

      // A slice that references the object.
      {ts: 17000, pid: 1, tid: 1, ph: 'B', cat: 'c', name: 'taskSlice', args: {my_object: {id_ref: '0x1000'}}}, // @suppress longLineCheck
      {ts: 17500, pid: 1, tid: 1, ph: 'E', cat: 'c', name: 'taskSlice', args: {}} // @suppress longLineCheck
    ];

    var m = new tracing.TraceModel();
    m.importTraces([events], false);
    var p1 = m.processes[1];

    var iA = p1.objects.getObjectInstanceAt('0x1000', 10);
    var s15 = iA.getSnapshotAt(15);

    var taskSlice = p1.threads[1].sliceGroup.slices[0];
    assertEquals(s15, taskSlice.args.my_object);
  });

  test('importIDRefsThatPointAtEachOther', function() {
    var events = [
      // An object.
      {ts: 10000, pid: 1, tid: 1, ph: 'N', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck
      {ts: 15000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: { // @suppress longLineCheck
        snapshot: { x: {
          id: 'foo/0x1001',
          value: 'bar'
        }}}},
      {ts: 50000, pid: 1, tid: 1, ph: 'D', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck

      // A slice that references the object.
      {ts: 17000, pid: 1, tid: 1, ph: 'B', cat: 'c', name: 'taskSlice', args: {my_object: {id_ref: '0x1001'}}}, // @suppress longLineCheck
      {ts: 17500, pid: 1, tid: 1, ph: 'E', cat: 'c', name: 'taskSlice', args: {}} // @suppress longLineCheck
    ];

    var m = new tracing.TraceModel();
    m.importTraces([events], false);
    var p1 = m.processes[1];

    var iA = p1.objects.getObjectInstanceAt('0x1000', 15);
    var iFoo = p1.objects.getObjectInstanceAt('0x1001', 15);
    assertNotUndefined(iA);
    assertNotUndefined(iFoo);

    var a15 = iA.getSnapshotAt(15);
    var foo15 = iFoo.getSnapshotAt(15);

    var taskSlice = p1.threads[1].sliceGroup.slices[0];
    assertEquals(foo15, taskSlice.args.my_object);
  });

  test('importDoesNotMutateEventList', function() {
    var events = [
      // An object.
      {ts: 10000, pid: 1, tid: 1, ph: 'N', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck
      {ts: 15000, pid: 1, tid: 1, ph: 'O', cat: 'c', id: '0x1000', name: 'a', args: { // @suppress longLineCheck
        snapshot: {foo: 15}}},
      {ts: 50000, pid: 1, tid: 1, ph: 'D', cat: 'c', id: '0x1000', name: 'a', args: {}}, // @suppress longLineCheck

      // A slice that references the object.
      {ts: 17000, pid: 1, tid: 1, ph: 'B', cat: 'c', name: 'taskSlice', args: {
        my_object: {id_ref: '0x1000'}}
      },
      {ts: 17500, pid: 1, tid: 1, ph: 'E', cat: 'c', name: 'taskSlice', args: {}} // @suppress longLineCheck
    ];

    // The A type family exists to mutate the args list provided to
    // snapshots.
    function ASnapshot() {
      tracing.trace_model.ObjectSnapshot.apply(this, arguments);
      this.args.foo = 7;
    }
    ASnapshot.prototype = {
      __proto__: tracing.trace_model.ObjectSnapshot.prototype
    };

    // Import event while the A types are registered, causing the
    // arguments of the snapshots to be mutated.
    var m = new tracing.TraceModel();
    try {
      tracing.trace_model.ObjectSnapshot.register('a', ASnapshot);
      m.importTraces([events], false);
    } finally {
      tracing.trace_model.ObjectSnapshot.unregister('a');
    }
    assertEquals(0, m.importErrors.length);

    // Verify that the events array wasn't modified.
    assertObjectEquals(
        events[1].args,
        {snapshot: {foo: 15}});
    assertObjectEquals(
        events[3].args,
        {my_object: {id_ref: '0x1000'}});
  });

  // TODO(nduca): one slice, two threads
  // TODO(nduca): one slice, two pids
});
