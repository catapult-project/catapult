// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.quad');
base.require('base.rect');

base.unittest.testSuite('base.quad', function() {
  test('pointInTri', function() {
    var res = base.vecInTriangle2(
        [0.25, 0.25],
        [0, 0],
        [1, 0],
        [0, 1]);
    assertTrue(res);
  });

  test('pointNotInTri', function() {
    var res = base.vecInTriangle2(
        [0.75, 0.75],
        [0, 0],
        [1, 0],
        [0, 1]);
    assertFalse(res);
  });

  test('pointInside', function() {
    var q = base.Quad.From4Vecs([0, 0],
                                [1, 0],
                                [1, 1],
                                [0, 1]);
    var res = q.vecInside([0.5, 0.5]);
    assertTrue(res);
  });

  test('pointNotInQuad', function() {
    var q = base.Quad.From4Vecs([0, 0],
                                [1, 0],
                                [1, 1],
                                [0, 1]);
    var res = q.vecInside([1.5, 0.5]);
    assertFalse(res);
  });

  test('isRectangle', function() {
    assertTrue(base.Quad.FromXYWH(0, 0, 10, 10).isRectangle());
    assertTrue(base.Quad.FromXYWH(-10, -10, 5, 5).isRectangle());
    assertTrue(base.Quad.FromXYWH(-10, -10, 20, 20).isRectangle());
    assertTrue(base.Quad.FromXYWH(-10, 10, 5, 5).isRectangle());

    assertFalse(base.Quad.FromXYWH(0, 0, -10, -10).isRectangle());
    assertFalse(base.Quad.From8Array([0, 1, 2, 3, 4, 5, 6, 7]).isRectangle());
    assertFalse(base.Quad.From8Array([0, 0, 0, 5, 5, 5, 0, 0]).isRectangle());
  });

  test('projectUnitRect', function() {
    var container = base.Quad.FromXYWH(0, 0, 10, 10);
    var srcRect = base.Rect.FromXYWH(0.1, 0.8, 0.8, 0.1);
    var expectedRect = srcRect.scale(10);

    var q = new base.Quad();
    container.projectUnitRectFast(q, srcRect);

    assertQuadEquals(base.Quad.FromRect(expectedRect), q);
  });

  test('projectUnitRectOntoUnitQuad', function() {
    var container = base.Quad.FromXYWH(0, 0, 1, 1);
    var srcRect = base.Rect.FromXYWH(0.0, 0, 1, 1);
    var expectedRect = srcRect;

    var q = new base.Quad();
    container.projectUnitRectFast(q, srcRect);

    assertQuadEquals(base.Quad.FromRect(expectedRect), q);
  });

  test('projectUnitRectOntoSizeTwoQuad', function() {
    var container = base.Quad.FromXYWH(0, 0, 2, 2);
    var srcRect = base.Rect.FromXYWH(0.0, 0, 1, 1);
    var expectedRect = srcRect.scale(2);

    var q = new base.Quad();
    container.projectUnitRectFast(q, srcRect);

    assertQuadEquals(base.Quad.FromRect(expectedRect), q);
  });

  test('projectUnitRectOntoTranslatedQuad', function() {
    var container = base.Quad.FromXYWH(1, 1, 1, 1);
    var srcRect = base.Rect.FromXYWH(0.0, 0, 1, 1);
    var expectedRect = srcRect.translate([1, 1]);

    var q = new base.Quad();
    container.projectUnitRectFast(q, srcRect);

    assertQuadEquals(base.Quad.FromRect(expectedRect), q);
  });

  test('projectShrunkUnitRectOntoUnitQuad', function() {
    var container = base.Quad.FromXYWH(0, 0, 1, 1);
    var srcRect = base.Rect.FromXYWH(0.1, 0.1, 0.8, 0.8);
    var expectedRect = srcRect;

    var q = new base.Quad();
    container.projectUnitRectFast(q, srcRect);

    assertQuadEquals(base.Quad.FromRect(expectedRect), q);
  });
});
