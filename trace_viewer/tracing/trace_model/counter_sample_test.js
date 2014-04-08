// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.trace_model.counter');

tvcm.unittest.testSuite('tracing.trace_model.counter_sample_test', function() {
  var Counter = tracing.trace_model.Counter;
  var CounterSeries = tracing.trace_model.CounterSeries;
  var CounterSample = tracing.trace_model.CounterSample;

  test('groupByTimestamp', function() {
    var counter = new Counter();
    var s0 = counter.addSeries(new CounterSeries('x', 0));
    var s1 = counter.addSeries(new CounterSeries('y', 1));

    var s0_0 = s0.addCounterSample(0, 100);
    var s0_1 = s1.addCounterSample(0, 200);
    var s1_0 = s0.addCounterSample(1, 100);
    var s1_1 = s1.addCounterSample(1, 200);

    var groups = CounterSample.groupByTimestamp([s0_1, s0_0,
                                                 s1_1, s1_0]);
    assertEquals(2, groups.length);
    assertArrayEquals([s0_0, s0_1], groups[0]);
    assertArrayEquals([s1_0, s1_1], groups[1]);
  });


  test('getSampleIndex', function() {
    var ctr = new Counter(null, 0, '', 'myCounter');
    var s0 = new CounterSeries('a', 0);
    ctr.addSeries(s0);

    var s0_0 = s0.addCounterSample(0, 0);
    var s0_1 = s0.addCounterSample(1, 100);
    assertEquals(0, s0_0.getSampleIndex());
    assertEquals(1, s0_1.getSampleIndex());
  });

});
