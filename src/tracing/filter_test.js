// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest');
base.require('tracing.test_utils');
base.require('tracing.filter');

base.unittest.testSuite('tracing.filter', function() {
  var TitleFilter = tracing.TitleFilter;
  var CategoryFilter = tracing.CategoryFilter;

  test('titleFilter', function() {
    var s0 = tracing.test_utils.newSliceNamed('a', 1, 3);
    assertFalse(new TitleFilter('').matchSlice(s0));

    assertTrue(new TitleFilter('a').matchSlice(s0));
    assertFalse(new TitleFilter('x').matchSlice(s0));

    var s1 = tracing.test_utils.newSliceNamed('ba', 1, 3);
    assertTrue(new TitleFilter('a').matchSlice(s1));
    assertTrue(new TitleFilter('ba').matchSlice(s1));
    assertFalse(new TitleFilter('x').matchSlice(s1));

    var s2 = tracing.test_utils.newSliceNamed('Ca', 1, 3);
    assertTrue(new TitleFilter('A').matchSlice(s2));
    assertTrue(new TitleFilter('cA').matchSlice(s2));
    assertFalse(new TitleFilter('X').matchSlice(s2));

    var c0 = tracing.test_utils.newCounterNamed(null, 'a');
    assertFalse(new TitleFilter('').matchCounter(c0));

    assertTrue(new TitleFilter('a').matchCounter(c0));
    assertFalse(new TitleFilter('x').matchCounter(c0));

    var c1 = tracing.test_utils.newCounterNamed(null, 'ba');
    assertTrue(new TitleFilter('a').matchCounter(c1));
    assertTrue(new TitleFilter('ba').matchCounter(c1));
    assertFalse(new TitleFilter('x').matchCounter(c1));

    var c2 = tracing.test_utils.newCounterNamed(null, 'cA');
    assertTrue(new TitleFilter('a').matchCounter(c2));
    assertTrue(new TitleFilter('Ca').matchCounter(c2));
    assertFalse(new TitleFilter('X').matchCounter(c2));
  });

  test('categoryFilter', function() {
    var sNoCategory = tracing.test_utils.newSliceNamed('a', 1, 3);
    sNoCategory.category = undefined;
    assertTrue(new CategoryFilter(['x']).matchSlice(sNoCategory));

    var s0 = tracing.test_utils.newSlice(1, 3);
    s0.category = 'x';
    assertFalse(new CategoryFilter(['x']).matchSlice(s0));

    var s1 = tracing.test_utils.newSliceNamed('ba', 1, 3);
    s1.category = 'y';
    assertTrue(new CategoryFilter(['x']).matchSlice(s1));
    assertFalse(new CategoryFilter(['y']).matchSlice(s1));
    assertFalse(new CategoryFilter(['x', 'y']).matchSlice(s1));

    var cNoCategory = tracing.test_utils.newCounterCategory(
        null, undefined, 'a');
    assertTrue(new CategoryFilter(['x']).matchCounter(cNoCategory));

    var c0 = tracing.test_utils.newCounterCategory(null, 'x', 'a');
    assertFalse(new CategoryFilter(['x']).matchCounter(c0));

    var c1 = tracing.test_utils.newCounterCategory(null, 'y', 'ba');
    assertTrue(new CategoryFilter(['x']).matchCounter(c1));
    assertFalse(new CategoryFilter(['y']).matchCounter(c1));
    assertFalse(new CategoryFilter(['x', 'y']).matchCounter(c1));
  });

  test('filterSliceArray', function() {
    var slices = [
      tracing.test_utils.newSliceNamed('ba', 1, 3),
      tracing.test_utils.newSliceNamed('ab', 1, 3),
      tracing.test_utils.newSliceNamed('x', 1, 3),
      tracing.test_utils.newSliceNamed('axa', 1, 3)
    ];
    var filter = new TitleFilter('a');
    var matched = tracing.filterSliceArray(filter, slices);
    assertEquals(3, matched.length);
    assertEquals('ba', matched[0].title);
    assertEquals('ab', matched[1].title);
    assertEquals('axa', matched[2].title);
  });

  test('filterCounterArray', function() {
    var counters = [
      tracing.test_utils.newCounterNamed(null, 'ba'),
      tracing.test_utils.newCounterNamed(null, 'ab'),
      tracing.test_utils.newCounterNamed(null, 'x'),
      tracing.test_utils.newCounterNamed(null, 'axa')
    ];
    var filter = new TitleFilter('a');
    var matched = tracing.filterCounterArray(filter, counters);
    assertEquals(3, matched.length);
    assertEquals('ba', matched[0].name);
    assertEquals('ab', matched[1].name);
    assertEquals('axa', matched[2].name);
  });
});
