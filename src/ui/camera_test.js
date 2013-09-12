// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('base.quad');
base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.quad_stack_view');

base.unittest.testSuite('ui.camera', function() {

  function createQuads() {
    var quads = [
      base.Quad.fromXYWH(-500, -500, 30, 30), // 4 corners
      base.Quad.fromXYWH(-500, 470, 30, 30),
      base.Quad.fromXYWH(470, -500, 30, 30),
      base.Quad.fromXYWH(470, 470, 30, 30),
      base.Quad.fromXYWH(-250, -250, 250, 250), // crosshairs
      base.Quad.fromXYWH(0, -250, 250, 250), // crosshairs
      base.Quad.fromXYWH(-250, 0, 250, 250), // crosshairs
      base.Quad.fromXYWH(0, 0, 250, 250) // crosshairs
    ];
    quads[0].stackingGroupId = 0;
    quads[1].stackingGroupId = 0;
    quads[2].stackingGroupId = 0;
    quads[3].stackingGroupId = 0;
    quads[4].stackingGroupId = 1;
    quads[5].stackingGroupId = 1;
    quads[6].stackingGroupId = 1;
    quads[7].stackingGroupId = 1;
    return quads;
  }

  function createQuadStackView(testFramework) {
    var quads = createQuads();
    var view = new ui.QuadStackView();
    // simulate the constraints of the layer-tree-view
    view.style.height = '400px';
    view.style.width = '800px';
    view.deviceRect = base.Rect.fromXYWH(-250, -250, 500, 500);
    view.quads = quads;

    testFramework.addHTMLOutput(view);
    return view;
  }

  test('initialState', function() {
    var view = createQuadStackView(this);

    var viewRect =
        view.getBoundingClientRect();
    assertEquals(400, viewRect.height);
    assertEquals(800, viewRect.width);
  });
});
