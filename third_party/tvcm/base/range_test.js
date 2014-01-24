// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.range');

base.unittest.testSuite('base.range', function() {
  test('addValue', function() {
    var range = new base.Range();
    assertTrue(range.isEmpty);
    range.addValue(1);
    assertFalse(range.isEmpty);
    assertEquals(range.min, 1);
    assertEquals(range.max, 1);

    range.addValue(2);
    assertFalse(range.isEmpty);
    assertEquals(range.min, 1);
    assertEquals(range.max, 2);
  });

  test('addNonEmptyRange', function() {
    var r1 = new base.Range();
    r1.addValue(1);
    r1.addValue(2);

    var r = new base.Range();
    r.addRange(r1);
    assertEquals(r.min, 1);
    assertEquals(r.max, 2);
  });

  test('addEmptyRange', function() {
    var r1 = new base.Range();

    var r = new base.Range();
    r.addRange(r1);
    assertTrue(r.isEmpty);
    assertEquals(r.min, undefined);
    assertEquals(r.max, undefined);
  });

  test('addRangeToRange', function() {
    var r1 = new base.Range();
    r1.addValue(1);
    r1.addValue(2);

    var r = new base.Range();
    r.addValue(3);
    r.addRange(r1);

    assertFalse(r.isEmpty);
    assertEquals(r.min, 1);
    assertEquals(r.max, 3);
  });
});
