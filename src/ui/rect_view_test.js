// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.bbox2');
base.require('base.quad');
base.require('ui.quad_stack');
base.require('ui.quad_view_viewport');
base.require('ui.rect_view');

base.unittest.testSuite('ui.rect_view', function() {

  test('rect_size', function() {
    var quads = [
      base.Quad.FromXYWH(0, 0, 640, 480),
      base.Quad.FromXYWH(0, -100, 640, 480),
      base.Quad.FromXYWH(100, 100, 640, 480)
    ];
    quads[0].stackingGroupId = 0;
    quads[1].stackingGroupId = 1;
    quads[2].stackingGroupId = 2;

    var quadsBbox = new base.BBox2();
    quads.forEach(function(quad) { quadsBbox.addQuad(quad); });

    var stack = new ui.QuadStack();

    var deviceViewportSizeForFrame = {width: 640, height: 480};
    stack.initialize(quadsBbox.asRect(), deviceViewportSizeForFrame);
    stack.quads = quads;

    this.addHTMLOutput(stack);

    var expected = stack.viewport.layoutPixelsPerWorldPixel *
        deviceViewportSizeForFrame.width + 'px';

    assertEquals(expected, stack.worldViewportRectView.style.width);

    expected = (stack.viewport.layoutPixelsPerWorldPixel *
        deviceViewportSizeForFrame.height) +
        stack.worldViewportRectView_.decorationHeight + 'px';

    assertEquals(expected, stack.worldViewportRectView.style.height);
  }, {dpiAware: true});
});
