// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.importer.trace_event_importer');
base.require('tracing.timeline_view');
base.require('tracing.timeline_viewport');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.tracks.drawing_container_perf_test', function() {  // @suppress longLineCheck
  function getSynchronous(url) {
    var req = new XMLHttpRequest();
    req.open('GET', url, false);
    req.send(null);
    return req.responseText;
  }

  var model = undefined;

  var drawingContainer;
  var viewportDiv;

  function timedDrawingContainerPerfTest(name, testFn, iterations) {

    function setUpOnce() {
      if (model !== undefined)
        return;
      var events = getSynchronous('/test_data/huge_trace.json');
      model = new tracing.TraceModel();
      model.importTraces([events], true);
    }

    function setUp() {
      setUpOnce();
      viewportDiv = document.createElement('div');

      if (this.name === 'drawTrackContents_softwareCanvas') {
        viewportDiv.width = '200px';
        viewportDiv.style.width = '200px';
      }

      this.addHTMLOutput(viewportDiv);

      var viewport = new tracing.TimelineViewport(viewportDiv);

      drawingContainer = new tracing.tracks.DrawingContainer(viewport);
      viewport.modelTrackContainer = drawingContainer;

      var modelTrack = new tracing.tracks.TraceModelTrack(viewport);
      drawingContainer.appendChild(modelTrack);

      modelTrack.model = model;

      viewportDiv.appendChild(drawingContainer);

      // Size the canvas.
      drawingContainer.updateCanvasSizeIfNeeded_();

      // Size the viewport.
      var w = drawingContainer.canvas.width;
      var min = model.bounds.min;
      var range = model.bounds.range;

      var boost = range * 0.15;
      var dt = new tracing.TimelineDisplayTransform();
      dt.xSetWorldBounds(min - boost, min + range + boost, w);
      modelTrack.viewport.setDisplayTransformImmediately(dt);
    };

    function tearDown() {
      viewportDiv.innerText = '';
      drawingContainer = undefined;
    }

    timedPerfTest(name, testFn, {
      setUp: setUp,
      tearDown: tearDown,
      iterations: iterations
    });
  }

  var n110100 = [1, 10, 100];
  n110100.forEach(function(val) {
    timedDrawingContainerPerfTest(
        'drawTrackContents_softwareCanvas_' + val,
        function() {
          drawingContainer.drawTrackContents_();
        }, val);
  });
});
