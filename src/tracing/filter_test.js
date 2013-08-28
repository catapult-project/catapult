// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest');
base.require('tracing.test_utils');
base.require('tracing.filter');

base.unittest.testSuite('tracing.filter', function() {
  var TitleFilter = tracing.TitleFilter;
  var ExactTitleFilter = tracing.ExactTitleFilter;
  var CategoryFilter = tracing.CategoryFilter;

  test('titleFilter', function() {
    assertThrows(function() {
      new TitleFilter();
    });
    assertThrows(function() {
      new TitleFilter('');
    });

    var s0 = tracing.test_utils.newSliceNamed('a', 1, 3);
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
  });

  test('exactTitleFilter', function() {
    assertThrows(function() {
      new ExactTitleFilter();
    });
    assertThrows(function() {
      new ExactTitleFilter('');
    });

    var s0 = tracing.test_utils.newSliceNamed('a', 1, 3);
    assertTrue(new ExactTitleFilter('a').matchSlice(s0));
    assertFalse(new ExactTitleFilter('b').matchSlice(s0));
    assertFalse(new ExactTitleFilter('A').matchSlice(s0));

    var s1 = tracing.test_utils.newSliceNamed('abc', 1, 3);
    assertTrue(new ExactTitleFilter('abc').matchSlice(s1));
    assertFalse(new ExactTitleFilter('Abc').matchSlice(s1));
    assertFalse(new ExactTitleFilter('bc').matchSlice(s1));
    assertFalse(new ExactTitleFilter('a').matchSlice(s1));
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
});
