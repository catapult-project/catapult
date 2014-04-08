// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.trace_model.counter');
tvcm.require('tracing.trace_model.counter_series');

tvcm.unittest.testSuite('tracing.trace_model.counter_test', function() {
  var Counter = tracing.trace_model.Counter;
  var CounterSeries = tracing.trace_model.CounterSeries;
  var CounterSample = tracing.trace_model.CounterSample;

  var createCounterWithTwoSeries = function() {
    var ctr = new Counter(null, 0, '', 'myCounter');
    var aSeries = new CounterSeries('a', 0);
    var bSeries = new CounterSeries('b', 0);
    ctr.addSeries(aSeries);
    ctr.addSeries(bSeries);

    aSeries.addCounterSample(0, 5);
    aSeries.addCounterSample(1, 6);
    aSeries.addCounterSample(2, 5);
    aSeries.addCounterSample(3, 7);

    bSeries.addCounterSample(0, 10);
    bSeries.addCounterSample(1, 15);
    bSeries.addCounterSample(2, 12);
    bSeries.addCounterSample(3, 16);

    return ctr;
  };

  test('getSampleStatisticsWithSingleSelection', function() {
    var ctr = createCounterWithTwoSeries();
    var ret = ctr.getSampleStatistics([0]);

    assertEquals(5, ret[0].min);
    assertEquals(5, ret[0].max);
    assertEquals(5, ret[0].avg);
    assertEquals(5, ret[0].start);
    assertEquals(5, ret[0].end);

    assertEquals(10, ret[1].min);
    assertEquals(10, ret[1].max);
    assertEquals(10, ret[1].avg);
    assertEquals(10, ret[1].start);
    assertEquals(10, ret[1].end);
  });

  test('getSampleStatisticsWithMultipleSelections', function() {
    var ctr = createCounterWithTwoSeries();
    var ret = ctr.getSampleStatistics([0, 1]);

    assertEquals(5, ret[0].min);
    assertEquals(6, ret[0].max);
    assertEquals((5 + 6) / 2, ret[0].avg);
    assertEquals(5, ret[0].start);
    assertEquals(6, ret[0].end);

    assertEquals(10, ret[1].min);
    assertEquals(15, ret[1].max);
    assertEquals((10 + 15) / 2, ret[1].avg);
    assertEquals(10, ret[1].start);
    assertEquals(15, ret[1].end);
  });

  test('getSampleStatisticsWithOutofOrderIndices', function() {
    var ctr = createCounterWithTwoSeries();
    var ret = ctr.getSampleStatistics([1, 0]);

    assertEquals(5, ret[0].min);
    assertEquals(6, ret[0].max);
    assertEquals((5 + 6) / 2, ret[0].avg);
    assertEquals(5, ret[0].start);
    assertEquals(6, ret[0].end);

    assertEquals(10, ret[1].min);
    assertEquals(15, ret[1].max);
    assertEquals((10 + 15) / 2, ret[1].avg);
    assertEquals(10, ret[1].start);
    assertEquals(15, ret[1].end);
  });

  test('getSampleStatisticsWithAllSelections', function() {
    var ctr = createCounterWithTwoSeries();
    var ret = ctr.getSampleStatistics([1, 0, 2, 3]);

    assertEquals(5, ret[0].min);
    assertEquals(7, ret[0].max);
    assertEquals((5 + 6 + 5 + 7) / 4, ret[0].avg);
    assertEquals(5, ret[0].start);
    assertEquals(7, ret[0].end);

    assertEquals(10, ret[1].min);
    assertEquals(16, ret[1].max);
    assertEquals((10 + 15 + 12 + 16) / 4, ret[1].avg);
    assertEquals(10, ret[1].start);
    assertEquals(16, ret[1].end);
  });
});
