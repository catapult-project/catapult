// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.v8_log_importer');

base.unittest.testSuite('tracing.importer.v8_log_importer', function() {
  var V8LogImporter = tracing.importer.V8LogImporter;

  test('tickEventInSharedLibrary', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'tick,0x99d8aae4,0xbff02f08,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'));
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8 PC');
    var t = threads[0];
    assertEquals(1, t.samples.length);
    assertEquals('/usr/lib/libc++.1.dylib', t.samples[0].title);
  });

  test('tickEventInGeneratedCode', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'code-creation,Stub,2,0x5b60ce80,1259,"StringAddStub"',
      'tick,0x5b60ce84,0xbff02f08,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'));
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8 PC');
    var t = threads[0];
    assertEquals(1, t.samples.length);
    assertEquals('StringAddStub', t.samples[0].title);
  });

  test('tickEventInUknownCode', function() {
    var lines = [
      'shared-library,"/usr/lib/libc++.1.dylib",0x99d8aae0,0x99dce729',
      'code-creation,Stub,2,0x5b60ce80,1259,"StringAddStub"',
      'tick,0x4,0xbff02f08,12158,0,0x0,5'];
    var m = new tracing.TraceModel(lines.join('\n'));
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8 PC');
    var t = threads[0];
    assertEquals(1, t.samples.length);
    assertEquals('UnknownCode', t.samples[0].title);
  });

  test('timerEventSliceCreation', function() {
    var lines = ['timer-event,"V8.External",38189483,3'];
    var m = new tracing.TraceModel(lines.join('\n'));
    var p = m.processes[-32];
    var threads = p.findAllThreadsNamed('V8 Timers');
    assertNotUndefined(threads);
    assertEquals(threads.length, 1);
    var t = threads[0];
    assertEquals(t.sliceGroup.length, 1);
  });

  test('processThreadCreation', function() {
    var lines = ['timer-event,"V8.External",38189483,3'];
    var m = new tracing.TraceModel(lines.join('\n'));
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
