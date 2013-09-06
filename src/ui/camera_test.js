// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('base.quad');
base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.quad_stack_viewer');

base.unittest.testSuite('ui.camera', function() {

  function createQuads() {
    var quads = [
      base.Quad.FromXYWH(-500, -500, 30, 30), // 4 corners
      base.Quad.FromXYWH(-500, 470, 30, 30),
      base.Quad.FromXYWH(470, -500, 30, 30),
      base.Quad.FromXYWH(470, 470, 30, 30),
      base.Quad.FromXYWH(-250, -250, 250, 250), // crosshairs
      base.Quad.FromXYWH(0, -250, 250, 250), // crosshairs
      base.Quad.FromXYWH(-250, 0, 250, 250), // crosshairs
      base.Quad.FromXYWH(0, 0, 250, 250), // crosshairs
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

  function createQuadStackViewer(testFramework) {
    var quads = createQuads();
    var viewer = new ui.QuadStackViewer();
    // simulate the constraints of the layer-tree-viewer
    viewer.style.height = '400px';
    viewer.style.width = '800px';
    viewer.deviceRect = base.Rect.FromXYWH(-250, -250, 500, 500);
    viewer.quads = quads;

    testFramework.addHTMLOutput(viewer);
    return viewer;
  }

  test('initialState', function() {
    var viewer = createQuadStackViewer(this);

    var viewerRect =
        viewer.getBoundingClientRect();
    assertEquals(400, viewerRect.height);
    assertEquals(800, viewerRect.width);
  });
});
