// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.trace_model');
tvcm.require('tracing.trace_model.kernel');

tvcm.unittest.testSuite('tracing.trace_model.kernel_test', function() {
  test('bestGuessAtCpuCountWithNoData', function() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
    });
    assertEquals(undefined, m.kernel.bestGuessAtCpuCount);
  });

  test('bestGuessAtCpuCountWithCpuData', function() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      var c1 = m.kernel.getOrCreateCpu(1);
      var c2 = m.kernel.getOrCreateCpu(2);
    });
    assertEquals(2, m.kernel.bestGuessAtCpuCount);
  });

  test('bestGuessAtCpuCountWithSoftwareCpuCount', function() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      m.kernel.softwareMeasuredCpuCount = 2;
    });
    assertEquals(2, m.kernel.bestGuessAtCpuCount);
  });

});
