// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.bbox2');
base.require('base.quad');
base.require('ui.quad_view');
base.require('ui.quad_view_viewport');

base.unittest.testSuite('ui.quad_view', function() {
  var Quad = base.Quad;
  var QuadView = ui.QuadView;
  var QuadViewViewport = ui.QuadViewViewport;

  test('instantiate', function() {
    var quadView = new QuadView();
    var quads = [
      Quad.FromXYWH(0, 0, 10, 10),
      Quad.FromXYWH(10, 10, 10, 10),
      Quad.FromXYWH(20, 4, 10, 10),
      Quad.FromXYWH(30, 10, 20, 20),
      Quad.FromXYWH(20, 20, 10, 10),
      Quad.FromXYWH(15, 15, 10, 10)
    ];
    quads[2].upperBorderColor = 'rgba(255,255,0,1)';
    quads[3].backgroundColor = 'rgba(255,0,255,0.15)';
    quads[3].borderColor = 'rgba(0,255,255,1)';
    var quadsBBox = new base.BBox2();
    for (var i = 0; i < quads.length; i++)
      quadsBBox.addQuad(quads[i]);

    quadView.title = 'Test Tree';
    quadView.quads = quads;
    quadView.viewport = new QuadViewViewport(quadsBBox.asRect(), 10.0);
    quadView.deviceViewportSizeForFrame = {width: 50, height: 30};

    quadView.addEventListener(
        'selectionChanged',
        function(e) {
          quads.forEach(function(q) {
            q.upperBorderColor = undefined;
          });

          e.selectedQuadIndices.forEach(function(i) {
            quads[i].upperBorderColor = 'rgba(255,255,0,1)';
          });
          quadView.quads = quads;
        }.bind(this));

    this.addHTMLOutput(quadView);
  });

  test('instantiate_backgroundTexture', function() {
    var quadView = new QuadView();
    var quads = [Quad.FromXYWH(0, 0, 10, 10)];
    var data = new Uint8Array(2 * 2 * 4);
    data[0] = 0;
    data[1] = 0;
    data[2] = 0;
    data[3] = 255;

    data[4] = 255;
    data[5] = 0;
    data[6] = 0;
    data[7] = 255;

    data[8] = 0;
    data[9] = 255;
    data[10] = 0;
    data[11] = 255;

    data[12] = 0;
    data[13] = 0;
    data[14] = 255;
    data[15] = 255;

    var quadsBBox = new base.BBox2();
    for (var i = 0; i < quads.length; i++)
      quadsBBox.addQuad(quads[i]);

    quadView.title = 'Test Tree';
    quadView.quads = quads;
    quadView.viewport = new QuadViewViewport(quadsBBox.asRect(), 50.0);

    this.addHTMLOutput(quadView);
  });

  test('instantiate_warpedTexturedQuad', function() {
    var quadView = new QuadView();
    var quads = [base.Quad.From8Array([0, 0,
                                       10, 0,
                                       10, 5,
                                       0, 10])];
    var data = new Uint8Array(2 * 2 * 4);
    data[0] = 0;
    data[1] = 0;
    data[2] = 0;
    data[3] = 255;

    data[4] = 255;
    data[5] = 0;
    data[6] = 0;
    data[7] = 255;

    data[8] = 0;
    data[9] = 255;
    data[10] = 0;
    data[11] = 255;

    data[12] = 0;
    data[13] = 0;
    data[14] = 255;
    data[15] = 255;
    var quadsBBox = new base.BBox2();
    for (var i = 0; i < quads.length; i++)
      quadsBBox.addQuad(quads[i]);

    quadView.title = 'Test Tree';
    quadView.quads = quads;
    quadView.viewport = new QuadViewViewport(quadsBBox.asRect(), 50.0);

    this.addHTMLOutput(quadView);
  });

  test('findTiles', function() {
    var quadView = new QuadView();
    var quads = [
      Quad.FromXYWH(0, 0, 10, 10),
      Quad.FromXYWH(10, 10, 10, 10),
      Quad.FromXYWH(20, 4, 10, 10),
      Quad.FromXYWH(30, 10, 20, 20),
      Quad.FromXYWH(20, 20, 10, 10),
      Quad.FromXYWH(15, 15, 10, 10)
    ];

    var quadsBBox = new base.BBox2();
    for (var i = 0; i < quads.length; i++)
      quadsBBox.addQuad(quads[i]);

    quadView.title = 'Test Tree';
    quadView.quads = quads;

    var deviceViewportSizeForFrame = {width: 50, height: 30};
    quadView.viewport = new QuadViewViewport(
        quadsBBox.asRect(), 10.0, 0, 2);

    var rect = quadView.canvas_.getBoundingClientRect();
    var hitIndices = quadView.findQuadsAtCanvasClientPoint(
        rect.left + 75, rect.top + 75);

    assertEquals(2, hitIndices.length);
    assertArrayEquals(hitIndices, [1, 5]);
  });
});
