// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.color');

base.unittest.testSuite('base.color', function() {
  test('fromRGB', function() {
    var c = base.Color.fromString('rgb(1, 2, 3)');
    assertEquals(1, c.r);
    assertEquals(2, c.g);
    assertEquals(3, c.b);
    assertEquals(undefined, c.a);
  });

  test('FromRGBA', function() {
    var c = base.Color.fromString('rgba(1, 2, 3, 0.5)');
    assertEquals(1, c.r);
    assertEquals(2, c.g);
    assertEquals(3, c.b);
    assertEquals(0.5, c.a);
  });

  test('fromHex', function() {
    var c = base.Color.fromString('#010203');
    assertEquals(1, c.r);
    assertEquals(2, c.g);
    assertEquals(3, c.b);
    assertEquals(undefined, c.a);
  });

  test('toStringRGB', function() {
    var c = new base.Color(1, 2, 3);
    assertEquals('rgb(1,2,3)', c.toString());
  });

  test('toStringRGBA', function() {
    var c = new base.Color(1, 2, 3, 0.5);
    assertEquals('rgba(1,2,3,0.5)', c.toString());
  });

  test('lerpRGB', function() {
    var a = new base.Color(0, 127, 191);
    var b = new base.Color(255, 255, 255);
    var x = base.Color.lerpRGB(a, b, 0.25);
    assertEquals(63, x.r);
    assertEquals(159, x.g);
    assertEquals(207, x.b);
  });

  test('lerpRGBA', function() {
    var a = new base.Color(0, 127, 191, 0.5);
    var b = new base.Color(255, 255, 255, 1);
    var x = base.Color.lerpRGBA(a, b, 0.25);
    assertEquals(63, x.r);
    assertEquals(159, x.g);
    assertEquals(207, x.b);
    assertEquals(0.625, x.a);
  });
});
