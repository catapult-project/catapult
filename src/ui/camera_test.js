// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.unittest');
base.require('base.bbox2');
base.require('ui.quad_stack');
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

  function createBbox(quads) {
    var quadsBbox = new base.BBox2();
    quads.forEach(function(quad) { quadsBbox.addQuad(quad); });
    return quadsBbox;
  }

  function checkPosition(viewer) {
    var viewedRect =
        viewer.quadStack.transformedContainer.getBoundingClientRect();
    var viewerRect = viewer.getBoundingClientRect();
    var deltaX = (viewerRect.left + viewerRect.width / 2) -
        (viewedRect.left + viewedRect.width / 2);
    assertTrue(Math.abs(deltaX) < 1);
    var deltaY = (viewerRect.top + viewerRect.height / 2) -
        (viewedRect.top + viewedRect.height / 2);
    assertTrue(Math.abs(deltaY) < 1);
  }

  function createQuadStackViewer(testFramework,
      opt_devicePixelsPerLayoutPixel) {
    var quads = createQuads();
    var viewer = new ui.QuadStackViewer();
    // simulate the constraints of the layer-tree-viewer
    viewer.style.height = '400px';
    viewer.style.width = '800px';
    var deviceViewportSizeForFrame = {width: 320, height: 460};
    viewer.quadStack.initialize(createBbox(quads).asRect(),
        deviceViewportSizeForFrame,
        undefined, opt_devicePixelsPerLayoutPixel);
    viewer.quadStack.quads = quads;

    testFramework.addHTMLOutput(viewer);
    return viewer;
  }

  test('initialState', function() {
    var viewer = createQuadStackViewer(this);
    // TODO this initial value is too high, but we can't change it
    // until we change the execution order to create the viewport before
    // the camera.
    assertEquals(0.5, viewer.camera.scheduledLayoutPixelsPerWorldPixel);
    assertEquals(0, viewer.camera.tiltAroundXInDegrees);
    assertEquals(0, viewer.camera.tiltAroundYInDegrees);
    assertEquals(0, viewer.camera.panXInLayoutPixels);
    assertEquals(0, viewer.camera.panYInLayoutPixels);

    viewer.camera.repaint();
    var transformedContainerStyle =
        window.getComputedStyle(viewer.quadStack.transformedContainer);
    // If the position is absolute, then the quad_stack is not clipped.
    // If the position is relative then the height of the transformedContainer
    // takes on the height of its child and tests fail.
    assertEquals('static', transformedContainerStyle.position);

    var viewerRect =
        viewer.getBoundingClientRect();
    // The container CSS must fix our sizes or we can't get correct tests.
    assertEquals(400, viewerRect.height);
    assertEquals(800, viewerRect.width);

    checkPosition(viewer);
  });

  test('maxZoom', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    var startZoom = viewer.camera.scheduledLayoutPixelsPerWorldPixel;
    var fill = viewer.camera.zoomToFillViewWithWorld();
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 0.9 * fill;
    assertEquals(startZoom, viewer.camera.scheduledLayoutPixelsPerWorldPixel);
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 100;
    assertEquals(startZoom, viewer.camera.scheduledLayoutPixelsPerWorldPixel);
  });

  test('camera-zoom', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    var fill = viewer.camera.zoomToFillViewWithWorld();
    var parentHeight = viewer.getBoundingClientRect().height;
    var expect = parentHeight / viewer.quadStack.viewport.worldRect.height;
    assertAlmostEquals(expect, fill);
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = fill;
    viewer.camera.repaint();
    assertEquals(fill, viewer.camera.scheduledLayoutPixelsPerWorldPixel);
  });

  test('camera-tilt-x', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    assertEquals(0, viewer.camera.tiltAroundXInDegrees);
    viewer.camera.repaint(); // lock down values
    var startingHeight =
        viewer.quadStack.transformedContainer.getBoundingClientRect().height;
    viewer.camera.tiltAroundXInDegrees = 45;
    viewer.camera.repaint();
    assertEquals(45, viewer.camera.tiltAroundXInDegrees);
    var delta = startingHeight - Math.sqrt(2) *
        viewer.quadStack.transformedContainer.getBoundingClientRect().height;
    // assertAlmostEqual has too tight bounds for this case.
    assertTrue(Math.abs(delta) < 0.001);
  });

  test('camera-tilt-y', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    assertEquals(0, viewer.camera.tiltAroundYInDegrees);
    viewer.camera.repaint(); // lock down values
    var startingWidth =
        viewer.quadStack.transformedContainer.getBoundingClientRect().width;
    viewer.camera.tiltAroundYInDegrees = 45;
    viewer.camera.repaint();
    assertEquals(45, viewer.camera.tiltAroundYInDegrees);
    // To verify the tilt, compare the size of the tilted edge with the
    // untilted size. The ratio should be sqrt(2) for 45 degree tilt.
    var delta = startingWidth - Math.sqrt(2) *
        viewer.quadStack.transformedContainer.getBoundingClientRect().width;
    // assertAlmostEqual has too tight bounds for this case.
    assertTrue(Math.abs(delta) < 0.0001);
  });

  test('maximumPan', function() {
    var viewer = createQuadStackViewer(this);  // 800 x 400
    viewer.quadStack.style.outline = '1px solid green';
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 1;  // 3000 x 3000
    viewer.camera.repaint();
    var maxPan = viewer.camera.maximumPanRect;
    // At the max the __ edge of the object meets the __ edge of the view.
    assertEquals(400 - 500, maxPan.left);
    assertEquals(500 - 400, maxPan.right);
    assertEquals(200 - 500, maxPan.top);
    assertEquals(500 - 200, maxPan.bottom);
  });

  test('camera-pan-x', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    viewer.style.overflow = 'hidden';
    assertEquals(0, viewer.camera.panXInLayoutPixels);

    var viewerRect =
        viewer.getBoundingClientRect();

    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 1.0;
    viewer.camera.rescale_(); // Simulate the auto-pixel-perfect rescaling.
    viewer.camera.repaint();

    var worldWidth = viewer.quadStack.viewport.unpaddedWorldRect.width;
    viewer.camera.panXInLayoutPixels = (viewerRect.width / 2) -
        (viewer.camera.scheduledLayoutPixelsPerWorldPixel * worldWidth / 2);
    viewer.camera.repaint();
    var viewedRect =
        viewer.quadStack.transformedContainer.getBoundingClientRect();
    // The right edge of the world is aligned with the right of the
    // viewer element.
    assertEquals(viewerRect.right, viewedRect.right);

    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 0.1;
    viewer.camera.repaint();
    var alignRight = (viewerRect.width / 2) -
        (viewer.camera.scheduledLayoutPixelsPerWorldPixel * worldWidth / 2);
    viewer.camera.panXInLayoutPixels = alignRight;
    // Verify that we did not hit the maximumPanRect
    assertEquals(alignRight, viewer.camera.panXInLayoutPixels);
    viewer.camera.repaint();
    viewedRect =
        viewer.quadStack.transformedContainer.getBoundingClientRect();
    assertEquals(viewerRect.right, viewedRect.right);
  });

  test('camera-pan-auto-scale', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    // The user starts from repainted/rescaled object.
    viewer.camera.repaint();
    viewer.camera.rescale_(); // Simulate the auto-pixel-perfect rescaling.
    // Then they pan to move the right edge in contact.
    var viewerRect =
        viewer.getBoundingClientRect();
    var worldWidth = viewer.quadStack.viewport.unpaddedWorldRect.width;
    var alignRight = (viewerRect.width / 2) -
        (viewer.camera.scheduledLayoutPixelsPerWorldPixel * worldWidth / 2);
    viewer.camera.panXInLayoutPixels = alignRight;

    viewer.camera.repaint();
    viewer.camera.rescale_();

    var viewedRect =
        viewer.quadStack.transformedContainer.getBoundingClientRect();
    assertEquals(viewerRect.right, viewedRect.right);
  });

  test('camera-pan-y', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    viewer.style.overflow = 'hidden';
    assertEquals(0, viewer.camera.panYInLayoutPixels);
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = 0.1;
    viewer.camera.rescale_(); // Simulate the auto-pixel-perfect rescaling.
    var viewerRect =
        viewer.getBoundingClientRect();
    var worldHeight = viewer.quadStack.viewport.unpaddedWorldRect.height;
    var alignBottom = (viewerRect.height / 2) -
        (viewer.camera.scheduledLayoutPixelsPerWorldPixel * worldHeight / 2);
    viewer.camera.panYInLayoutPixels = alignBottom;
    // Verify that we did not hit the maximumPanRect
    assertEquals(alignBottom, viewer.camera.panYInLayoutPixels);
    viewer.camera.repaint();
    var viewedRect =
        viewer.quadStack.transformedContainer.getBoundingClientRect();

    assertEquals(viewerRect.bottom, viewedRect.bottom);
  });

  test('camera-devicePixelsPerWorldPixel', function() {
    var viewer = createQuadStackViewer(this);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';
    viewer.quadStack.viewport.devicePixelsPerWorldPixel = 1.0;
    var fill = viewer.camera.zoomToFillViewWithWorld();
    viewer.camera.repaint();
    var parentHeight = viewer.getBoundingClientRect().height;
    var expect = parentHeight / viewer.quadStack.viewport.worldRect.height;
    assertAlmostEquals(expect, fill);
    viewer.camera.scheduledLayoutPixelsPerWorldPixel = fill;
    viewer.camera.repaint();
    checkPosition(viewer);
  });

  test('camera-devicePixelsPerLayoutPixel', function() {
    var viewer = createQuadStackViewer(this, 2);
    viewer.quadStack.transformedContainer.style.outline = '1px solid green';

    viewer.camera.repaint();
    checkPosition(viewer);
  }, {dpiAware: true});

});
