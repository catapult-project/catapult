// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.iteration_helpers');

base.unittest.testSuite('base.iteration_helpers', function() {
  var comparePossiblyUndefinedValues = base.comparePossiblyUndefinedValues;
  var compareArrays = base.compareArrays;

  test('comparePossiblyUndefinedValues', function() {
    function cmp(x, y) {
      assertNotUndefined(x);
      assertNotUndefined(y);
      return x - y;
    }

    assertTrue(comparePossiblyUndefinedValues(0, 1, cmp) < 0);
    assertTrue(comparePossiblyUndefinedValues(1, 0, cmp) > 0);
    assertTrue(comparePossiblyUndefinedValues(1, 1, cmp) == 0);

    assertTrue(comparePossiblyUndefinedValues(0, undefined, cmp) < 0);
    assertTrue(comparePossiblyUndefinedValues(undefined, 0, cmp) > 0);
    assertTrue(comparePossiblyUndefinedValues(undefined, undefined, cmp) == 0);
  });

  test('compareArrays', function() {
    function cmp(x, y) {
      assertNotUndefined(x);
      assertNotUndefined(y);
      return x - y;
    }

    assertTrue(compareArrays([1], [2], cmp) < 0);
    assertTrue(compareArrays([2], [1], cmp) > 0);

    assertTrue(compareArrays([1], [1, 2], cmp) < 0);
    assertTrue(compareArrays([1, 2], [1], cmp) > 0);

    assertTrue(compareArrays([], [1], cmp) < 0);
    assertTrue(compareArrays([1], [], cmp) > 0);

    assertTrue(compareArrays([2], [1], cmp) > 0);

    assertTrue(compareArrays([], [], cmp) == 0);
    assertTrue(compareArrays([1], [1], cmp) == 0);
  });
});
