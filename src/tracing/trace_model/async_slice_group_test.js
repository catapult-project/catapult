// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.trace_model.async_slice_group', function() {
  var Process = tracing.trace_model.Process;
  var Thread = tracing.trace_model.Thread;
  var AsyncSlice = tracing.trace_model.AsyncSlice;
  var AsyncSliceGroup = tracing.trace_model.AsyncSliceGroup;
  var newAsyncSlice = tracing.test_utils.newAsyncSlice;

  test('asyncSliceGroupBounds_Empty', function() {
    var g = new AsyncSliceGroup();
    g.updateBounds();
    assertTrue(g.bounds.isEmpty);
  });

  test('asyncSliceGroupBounds_Basic', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();
    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(1, 1.5, t1, t1));
    assertEquals(2, g.length);
    g.updateBounds();
    assertEquals(0, g.bounds.min);
    assertEquals(2.5, g.bounds.max);
  });

  test('asyncSlice_toJSON', function() {
    var js = [
      '{',
      '  "category" : "",',
      '  "title" : "a",',
      '  "colorId" : 0,',
      '  "start" : 0,',
      '  "didNotFinish" : false,',
      '  "duration" : 1,',
      '  "startThread" : __T1_GUID__,',
      '  "endThread" : __T1_GUID__,',
      '  "subSlices" : [ {',
      '        "category" : "",',
      '        "title" : "a",',
      '        "colorId" : 0,',
      '        "start" : 0,',
      '        "didNotFinish" : false,',
      '        "duration" : 1,',
      '        "startThread" : __T1_GUID__,',
      '        "endThread" : __T1_GUID__',
      '      } ]',
      '}'].join('\n');

    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var s = newAsyncSlice(0, 1, t1, t1);

    // Replace __T1_GUID__ with t1's actual GUID
    js = js.replace(/__T1_GUID__/g, t1.guid);

    // Modify whitespace of "js" so that string compare with another
    // JSON.stringified version can succeed.
    js = JSON.stringify(JSON.parse(js));

    assertEquals(js, JSON.stringify(s));
  });
});
