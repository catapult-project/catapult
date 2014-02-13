// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.rect');
tvcm.require('tvcm.quad');
tvcm.require('tvcm.unittest');
tvcm.require('tvcm.bbox2');
tvcm.require('tvcm.ui.quad_stack_view');

tvcm.unittest.testSuite('tvcm.ui.camera_test', function() {

  function createQuads() {
    var quads = [
      tvcm.Quad.fromXYWH(-500, -500, 30, 30), // 4 corners
      tvcm.Quad.fromXYWH(-500, 470, 30, 30),
      tvcm.Quad.fromXYWH(470, -500, 30, 30),
      tvcm.Quad.fromXYWH(470, 470, 30, 30),
      tvcm.Quad.fromXYWH(-250, -250, 250, 250), // crosshairs
      tvcm.Quad.fromXYWH(0, -250, 250, 250), // crosshairs
      tvcm.Quad.fromXYWH(-250, 0, 250, 250), // crosshairs
      tvcm.Quad.fromXYWH(0, 0, 250, 250) // crosshairs
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
    var view = new tvcm.ui.QuadStackView();
    // simulate the constraints of the layer-tree-view
    view.style.height = '400px';
    view.style.width = '800px';
    view.deviceRect = tvcm.Rect.fromXYWH(-250, -250, 500, 500);
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
