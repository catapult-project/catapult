// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.bbox2');
base.require('ui.quad_view_viewport');

base.unittest.testSuite('ui.quad_view_viewport', function() {
  var QuadViewViewport = ui.QuadViewViewport;

  test('basicsHighDPIUnpadded', function() {
    var bbox = new base.BBox2();
    bbox.addXY(0, 0);
    bbox.addXY(4000, 2000);

    var vp = new QuadViewViewport(bbox.asRect(), 0.125, 0, 2);

    assertEquals(500, vp.worldWidthInDevicePixels_);
    assertEquals(250, vp.worldHeightInDevicePixels_);

    assertEquals(250, vp.layoutRect_.width);
    assertEquals(125, vp.layoutRect_.height);

    // Top left.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(0, 0));
    assertEquals(0, tmp[0]);
    assertEquals(0, tmp[1]);

    // World center.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(125, 62.5));
    assertEquals(2000, tmp[0]);
    assertEquals(1000, tmp[1]);

    // Bottom right.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(250, 125));
    assertEquals(4000, tmp[0]);
    assertEquals(2000, tmp[1]);

    assertRectEquals(bbox.asRect(), vp.unpaddedWorldRect);
  });

  test('basicsHighDPI', function() {
    var bbox = new base.BBox2();
    bbox.addXY(0, 0);
    bbox.addXY(4000, 2000);

    var vp = new QuadViewViewport(bbox.asRect(), 0.125, 0.1, 2);
    assertEquals(550, vp.worldWidthInDevicePixels_);
    assertEquals(300, vp.worldHeightInDevicePixels_);

    assertEquals(275, vp.layoutRect_.width);
    assertEquals(150, vp.layoutRect_.height);

    // Top left.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(0, 0));
    assertEquals(-200, tmp[0]);
    assertEquals(-200, tmp[1]);

    // World center.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(137.5, 75));
    assertEquals(2000, tmp[0]);
    assertEquals(1000, tmp[1]);

    // Bottom right.
    var tmp = vp.layoutPixelsToWorldPixels(vec2.createXY(275, 150));
    assertEquals(4200, tmp[0]);
    assertEquals(2200, tmp[1]);

    assertRectEquals(bbox.asRect(), vp.unpaddedWorldRect);
  });
});
