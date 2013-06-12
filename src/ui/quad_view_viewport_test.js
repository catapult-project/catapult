// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('base.bbox2');
base.require('ui.quad_view_viewport');

'use strict';

base.unittest.testSuite('ui.quad_view_viewport', function() {
  var QuadViewViewport = ui.QuadViewViewport;

  test('basicsHighDPI', function() {
    var bbox = new base.BBox2();
    bbox.addXY(0, 0);
    bbox.addXY(4000, 2000);

    var vp = new QuadViewViewport(bbox, 0.125, null, 0, 2);
    assertEquals(500, vp.deviceWidth);
    assertEquals(250, vp.deviceHeight);

    assertEquals(250, vp.layoutRect.width);
    assertEquals(125, vp.layoutRect.height);

    // Top left.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(0, 0));
    assertEquals(0, tmp[0]);
    assertEquals(0, tmp[1]);

    // World center.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(125, 62.5));
    assertEquals(2000, tmp[0]);
    assertEquals(1000, tmp[1]);

    // Bottom right.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(250, 125));
    assertEquals(4000, tmp[0]);
    assertEquals(2000, tmp[1]);
  });

  test('basicsHighDPIUnpadded', function() {
    var bbox = new base.BBox2();
    bbox.addXY(0, 0);
    bbox.addXY(4000, 2000);

    var vp = new QuadViewViewport(bbox, 0.125, null, 0.1, 2);
    assertEquals(550, vp.deviceWidth);
    assertEquals(300, vp.deviceHeight);

    assertEquals(275, vp.layoutRect.width);
    assertEquals(150, vp.layoutRect.height);

    // Top left.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(0, 0));
    assertEquals(-200, tmp[0]);
    assertEquals(-200, tmp[1]);

    // World center.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(137.5, 75));
    assertEquals(2000, tmp[0]);
    assertEquals(1000, tmp[1]);

    // Bottom right.
    var tmp = vp.layoutPixelsToWorldPixels2(vec2.createXY(275, 150));
    assertEquals(4200, tmp[0]);
    assertEquals(2200, tmp[1]);
  });
});
