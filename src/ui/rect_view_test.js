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
      base.Quad.FromXYWH(100, 100, 300, 400),
      base.Quad.FromXYWH(100, 100, 100, 100)
    ];
    quads[0].stackingGroupId = 0;
    quads[1].stackingGroupId = 1;

    var quadsBbox = new base.BBox2();
    quads.forEach(function(quad) { quadsBbox.addQuad(quad); });

    var stack = new ui.QuadStack();

    var deviceViewportSizeForFrame = {width: 1000, height: 400};
    stack.initialize(quadsBbox.asRect(), deviceViewportSizeForFrame);
    stack.quads = quads;

    this.addHTMLOutput(stack);

    assertEquals('125px', stack.worldViewportRectView.style.width);
    assertEquals((50 + 36) + 'px', stack.worldViewportRectView.style.height);
  });
});
