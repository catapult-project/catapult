// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.quad_stack');

base.unittest.testSuite('ui.quad_stack', function() {
  test('instantiate', function() {
    var quads = [
      base.Quad.FromXYWH(0, -100, 100, 400),
      base.Quad.FromXYWH(0, 0, 100, 25),
      base.Quad.FromXYWH(100, 0, 10, 100)
    ];
    quads[0].stackingGroupId = 0;
    quads[1].stackingGroupId = 1;
    quads[2].stackingGroupId = 2;

    var quadsBbox = new base.BBox2();
    quads.forEach(function(quad) { quadsBbox.addQuad(quad); });

    var stack = new ui.QuadStack();
    if (stack.debug)
      throw new Error('ui.QuadStack debug flag must not be truthy.');

    stack.quads = quads;
    var deviceViewportSizeForFrame = {width: 100, height: 100};
    stack.viewport = new ui.QuadViewViewport(quadsBbox.asRect(),
        0.5, deviceViewportSizeForFrame);
    stack.style.border = '1px solid black';

    this.addHTMLOutput(stack);
  });
});
