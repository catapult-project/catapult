// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.trace_model.counter');

'use strict';

base.unittest.testSuite('tracing.trace_model.counter', function() {
  var createCounterWithTwoSeries = function() {
    var ctr = new tracing.trace_model.Counter(null, 0, '', 'myCounter');
    ctr.seriesNames.push('a', 'b');
    ctr.seriesColors.push(0, 1);
    ctr.timestamps.push(0, 1, 2, 3);
    ctr.samples.push(5, 10, 6, 15, 5, 12, 7, 16);
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
