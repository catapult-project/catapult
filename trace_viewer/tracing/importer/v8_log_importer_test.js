// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.importer.v8_log_importer');

tvcm.unittest.testSuite('tracing.importer.v8_log_importer_test', function() {
  var V8LogImporter = tracing.importer.V8LogImporter;

  test('tickEventInSharedLibrary', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'tick,0x99d8aae4,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var t = p.findAllThreadsNamed('V8')[0];
    assertEquals(1, t.samples.length);
    assertEquals('V8 PC', t.samples[0].title);
    assertEquals(12158 / 1000, t.samples[0].start);
    assertEquals('/usr/lib/libc++.1.dylib', t.samples[0].leafStackFrame.title);
  });

  test('tickEventInGeneratedCode', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'code-creation,Stub,2,0x5b60ce80,1259,"StringAddStub"',
      'tick,0x5b60ce84,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8');
    var t = threads[0];
    assertEquals(1, t.samples.length);
    assertEquals('StringAddStub', t.samples[0].leafStackFrame.title);
  });

  test('tickEventInUknownCode', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'code-creation,Stub,2,0x5b60ce80,1259,"StringAddStub"',
      'tick,0x4,0xbff02f08,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8');
    var t = threads[0];
    assertEquals(1, t.samples.length);
    assertEquals('Unknown', t.samples[0].leafStackFrame.title);
  });

  test('tickEventWithStack', function() {
    var lines = [
      'code-creation,LazyCompile,0,0x2905d0c0,1800,"InstantiateFunction native apinatives.js:26:29",0x56b19124,', // @suppress longLineCheck
      'tick,0x7fc6fe34,528674,0,0x3,0,0x2905d304'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var t = p.findAllThreadsNamed('V8')[0];
    assertEquals(1, t.samples.length);
    assertArrayEquals(
        ['v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[0].getUserFriendlyStackTrace());
  });

  test('twoTickEventsWithStack', function() {
    var lines = [
      'code-creation,LazyCompile,0,0x2905d0c0,1800,"InstantiateFunction native apinatives.js:26:29",0x56b19124,', // @suppress longLineCheck
      'tick,0x7fc6fe34,528674,0,0x3,0,0x2905d304',
      'tick,0x7fd2a534,536213,0,0x81d8d080,0,0x2905d304'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var t = p.findAllThreadsNamed('V8')[0];
    assertEquals(2, t.samples.length);
    assertEquals(528674 / 1000, t.samples[0].start);
    assertEquals(536213 / 1000, t.samples[1].start);
    assertArrayEquals(
        ['v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[0].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[1].getUserFriendlyStackTrace());
    assertEquals(t.samples[0].leafStackFrame,
                 t.samples[1].leafStackFrame);
  });

  test('twoTickEventsWithTwoStackFrames', function() {
    var lines = [
      'code-creation,LazyCompile,0,0x2904d560,876,"Instantiate native apinatives.js:9:21",0x56b190c8,~', // @suppress longLineCheck
      'code-creation,LazyCompile,0,0x2905d0c0,1800,"InstantiateFunction native apinatives.js:26:29",0x56b19124,', // @suppress longLineCheck
      'tick,0x7fc6fe34,528674,0,0x3,0,0x2905d304,0x2904d6e8',
      'tick,0x7fd2a534,536213,0,0x81d8d080,0,0x2905d304,0x2904d6e8'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var t = p.findAllThreadsNamed('V8')[0];
    assertEquals(2, t.samples.length);

    assertEquals(528674 / 1000, t.samples[0].start);
    assertEquals(536213 / 1000, t.samples[1].start);
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[0].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[1].getUserFriendlyStackTrace());

    var childStackFrame = t.samples[0].leafStackFrame;
    assertEquals(childStackFrame, t.samples[1].leafStackFrame);
    assertEquals(0, childStackFrame.children.length);

    var parentStackFrame = childStackFrame.parentFrame;
    assertEquals(1, parentStackFrame.children.length);
    assertEquals(childStackFrame, parentStackFrame.children[0]);

  });

  test('threeTickEventsWithTwoStackFrames', function() {
    var lines = [
      'code-creation,LazyCompile,0,0x2904d560,876,"Instantiate native apinatives.js:9:21",0x56b190c8,~', // @suppress longLineCheck
      'code-creation,LazyCompile,0,0x2905d0c0,1800,"InstantiateFunction native apinatives.js:26:29",0x56b19124,', // @suppress longLineCheck
      'tick,0x7fd7f75c,518328,0,0x81d86da8,2,0x2904d6e8',
      'tick,0x7fc6fe34,528674,0,0x3,0,0x2905d304,0x2904d6e8',
      'tick,0x7fd2a534,536213,0,0x81d8d080,0,0x2905d304,0x2904d6e8'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8');

    var t = threads[0];
    assertEquals(3, t.samples.length);
    assertEquals(518328 / 1000, t.samples[0].start);
    assertEquals(528674 / 1000, t.samples[1].start);
    assertEquals(536213 / 1000, t.samples[2].start);
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21'],
        t.samples[0].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[1].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[2].getUserFriendlyStackTrace());

    var topLevelStackFrame = t.samples[0].leafStackFrame;
    var childStackFrame = t.samples[1].leafStackFrame;
    assertEquals(childStackFrame, t.samples[2].leafStackFrame);
    assertEquals(topLevelStackFrame, childStackFrame.parentFrame);
    assertEquals(1, topLevelStackFrame.children.length);
    assertEquals(0, childStackFrame.children.length);
    assertEquals(childStackFrame, topLevelStackFrame.children[0]);
  });

  test('twoSubStacks', function() {
    var lines = [
      'code-creation,LazyCompile,0,0x2904d560,876,"Instantiate native apinatives.js:9:21",0x56b190c8,~', // @suppress longLineCheck
      'code-creation,LazyCompile,0,0x2905d0c0,1800,"InstantiateFunction native apinatives.js:26:29",0x56b19124,', // @suppress longLineCheck
      'tick,0x7fd7f75c,518328,0,0x81d86da8,2,0x2904d6e8',
      'tick,0x7fc6fe34,528674,0,0x3,0,0x2905d304,0x2904d6e8',
      'tick,0x7fd2a534,536213,0,0x81d8d080,0,0x2905d304,0x2904d6e8',
      'code-creation,Script,0,0x2906a7c0,792,"http://www.google.com/",0x5b12fe50,~', // @suppress longLineCheck
      'tick,0xb6f51d30,794049,0,0xb6f7b368,2,0x2906a914',
      'tick,0xb6f51d30,799146,0,0xb6f7b368,0,0x2906a914'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8');
    var t = threads[0];
    assertEquals(5, t.samples.length);

    assertEquals(518328 / 1000, t.samples[0].start);
    assertEquals(528674 / 1000, t.samples[1].start);
    assertEquals(536213 / 1000, t.samples[2].start);
    assertEquals(794049 / 1000, t.samples[3].start);
    assertEquals(799146 / 1000, t.samples[4].start);

    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21'],
        t.samples[0].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[1].getUserFriendlyStackTrace());
    assertArrayEquals(
        ['v8: Instantiate native apinatives.js:9:21',
         'v8: InstantiateFunction native apinatives.js:26:29'],
        t.samples[2].getUserFriendlyStackTrace());
    assertArrayEquals(['v8: http://www.google.com/'],
                      t.samples[3].getUserFriendlyStackTrace());
    assertArrayEquals(['v8: http://www.google.com/'],
                      t.samples[4].getUserFriendlyStackTrace());

    var firsStackTopLevelStackFrame = t.samples[0].leafStackFrame;
    var firsStackChildStackFrame = t.samples[1].leafStackFrame;
    assertEquals(firsStackChildStackFrame, t.samples[2].leafStackFrame);
    assertEquals(firsStackTopLevelStackFrame,
                 firsStackChildStackFrame.parentFrame);
    assertEquals(1, firsStackTopLevelStackFrame.children.length);
    assertEquals(0, firsStackChildStackFrame.children.length);
    assertEquals(firsStackChildStackFrame,
                 firsStackTopLevelStackFrame.children[0]);

    var secondStackStackFrame = t.samples[3].leafStackFrame;
    assertEquals(secondStackStackFrame, t.samples[4].leafStackFrame);
    assertEquals(0, secondStackStackFrame.children.length);
    assertEquals(undefined, secondStackStackFrame.parentFrame);
  });

  test('timerEventSliceCreation', function() {
    var lines = ['timer-event,"V8.External",38189483,3'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8 Timers');
    assertNotUndefined(threads);
    assertEquals(1, threads.length);
    var t = threads[0];
    assertEquals(1, t.sliceGroup.length);
  });

  test('processThreadCreation', function() {
    var lines = ['timer-event,"V8.External",38189483,3'];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertNotUndefined(m);
    var p = m.processes[-32];
    assertNotUndefined(p);
    var threads = p.findAllThreadsNamed('V8 Timers');
    assertNotUndefined(threads);
    assertEquals(threads.length, 1);
    var t = threads[0];
    assertEquals(t.name, 'V8 Timers');
  });

  test('canImport', function() {
    assertTrue(V8LogImporter.canImport(
        'timer-event,"V8.External",38189483,3'));
    assertFalse(V8LogImporter.canImport(''));
    assertFalse(V8LogImporter.canImport([]));
  });
});
