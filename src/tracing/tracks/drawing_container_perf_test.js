// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.importer.trace_event_importer');
base.require('tracing.timeline_view');
base.require('tracing.timeline_viewport');
base.require('tracing.trace_model');

base.unittest.perfTestSuite('tracing.tracks.drawing_container_perf', function() {  // @suppress longLineCheck
  function getSynchronous(url) {
    var req = new XMLHttpRequest();
    req.open('GET', url, false);
    req.send(null);
    return req.responseText;
  }

  var events = '';
  var model = undefined;
  setupOnce(function() {
    events = getSynchronous('/test_data/huge_trace.json');
    model = new tracing.TraceModel();
    model.importTraces([events], true);
  });

  var drawingContainer;
  var viewportDiv;
  setup(function() {
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
    track.viewport.setDisplayTransformImmediately(dt);
  });

  teardown(function() {
    viewportDiv.innerText = '';
    drawingContainer = undefined;
  });

  [1, 10, 100].forEach(function(val) {
    timedPerfTest('drawTrackContents_softwareCanvas', function() {
      drawingContainer.drawTrackContents_();
    }, {iterations: val});
  });
});
