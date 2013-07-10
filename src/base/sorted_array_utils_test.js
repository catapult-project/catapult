// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.sorted_array_utils');

base.unittest.testSuite('base.sorted_array_utils', function() {
  var ArrayOfIntervals = function(array) {
    this.array = array;
  }

  ArrayOfIntervals.prototype = {
    findLowIndex: function(ts) {
      return base.findLowIndexInSortedIntervals(
          this.array,
          function(x) { return x.lo; },
          function(x) { return x.hi - x.lo; },
          ts);
    }
  };

  test('findLow', function() {
    var array = new ArrayOfIntervals([
      {lo: 10, hi: 15},
      {lo: 20, hi: 30}
    ]);

    assertEquals(-1, array.findLowIndex(0));
    assertEquals(0, array.findLowIndex(10));
    assertEquals(0, array.findLowIndex(12));
    assertEquals(0, array.findLowIndex(14.9));

    // These two are a little odd... the return is correct in that
    // it was not found, but its neither below, nor above. Whatever.
    assertEquals(2, array.findLowIndex(15));
    assertEquals(2, array.findLowIndex(16));

    assertEquals(1, array.findLowIndex(20));
    assertEquals(1, array.findLowIndex(21));
    assertEquals(1, array.findLowIndex(29.99));

    assertEquals(2, array.findLowIndex(30));
    assertEquals(2, array.findLowIndex(40));
  });
});
