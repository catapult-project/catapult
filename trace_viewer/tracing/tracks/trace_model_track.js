// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.tracks.trace_model_track');

tvcm.require('tvcm.measuring_stick');
tvcm.require('tracing.tracks.container_track');
tvcm.require('tracing.tracks.kernel_track');
tvcm.require('tracing.tracks.process_track');
tvcm.require('tracing.draw_helpers');
tvcm.require('tvcm.ui');

tvcm.exportTo('tracing.tracks', function() {

  /**
   * Visualizes a Model by building ProcessTracks and
   * CpuTracks.
   * @constructor
   */
  var TraceModelTrack = tvcm.ui.define(
      'trace-model-track', tracing.tracks.ContainerTrack);

  TraceModelTrack.prototype = {

    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.ContainerTrack.prototype.decorate.call(this, viewport);
      this.classList.add('model-track');
    },

    detach: function() {
      tracing.tracks.ContainerTrack.prototype.detach.call(this);
    },

    get model() {
      return this.model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateContents_();
    },

    get hasVisibleContent() {
      return this.children.length > 0;
    },

    updateContents_: function() {
      this.textContent = '';
      if (!this.model_)
        return;

      this.appendKernelTrack_();

      // Get a sorted list of processes.
      var processes = this.model_.getAllProcesses();
      processes.sort(tracing.trace_model.Process.compare);

      for (var i = 0; i < processes.length; ++i) {
        var process = processes[i];

        var track = new tracing.tracks.ProcessTrack(this.viewport);
        track.process = process;
        if (!track.hasVisibleContent)
          continue;

        this.appendChild(track);
      }
      this.viewport_.rebuildEventToTrackMap();
    },

    addEventsToTrackMap: function(eventToTrackMap) {
      if (!this.model_)
        return;

      var tracks = this.children;
      for (var i = 0; i < tracks.length; ++i)
        tracks[i].addEventsToTrackMap(eventToTrackMap);

      if (this.instantEvents === undefined)
        return;

      var vp = this.viewport_;
      this.instantEvents.forEach(function(ev) {
        eventToTrackMap.addEvent(ev, this);
      }.bind(this));
    },

    appendKernelTrack_: function() {
      var kernel = this.model.kernel;
      var track = new tracing.tracks.KernelTrack(this.viewport);
      track.kernel = this.model.kernel;
      if (!track.hasVisibleContent)
        return;
      this.appendChild(track);
    },

    drawTrack: function(type) {
      var ctx = this.context();

      var pixelRatio = window.devicePixelRatio || 1;
      var bounds = this.getBoundingClientRect();
      var canvasBounds = ctx.canvas.getBoundingClientRect();

      ctx.save();
      ctx.translate(0, pixelRatio * (bounds.top - canvasBounds.top));

      var dt = this.viewport.currentDisplayTransform;
      var viewLWorld = dt.xViewToWorld(0);
      var viewRWorld = dt.xViewToWorld(bounds.width * pixelRatio);

      switch (type) {
        case tracing.tracks.DrawType.GRID:
          this.viewport.drawMajorMarkLines(ctx);
          // The model is the only thing that draws grid lines.
          ctx.restore();
          return;

        case tracing.tracks.DrawType.FLOW_ARROWS:
          if (this.model_.flowIntervalTree.size === 0) {
            ctx.restore();
            return;
          }

          this.drawFlowArrows_(viewLWorld, viewRWorld);
          ctx.restore();
          return;

        case tracing.tracks.DrawType.INSTANT_EVENT:
          if (!this.model_.instantEvents ||
              this.model_.instantEvents.length === 0)
            break;

          tracing.drawInstantSlicesAsLines(
              ctx,
              this.viewport.currentDisplayTransform,
              viewLWorld,
              viewRWorld,
              bounds.height,
              this.model_.instantEvents,
              1);

          break;

        case tracing.tracks.DrawType.MARKERS:
          if (!this.viewport.interestRange.isEmpty) {
            this.viewport.interestRange.draw(ctx, viewLWorld, viewRWorld);
            this.viewport.interestRange.drawIndicators(
                ctx, viewLWorld, viewRWorld);
          }
          ctx.restore();
          return;
      }
      ctx.restore();

      tracing.tracks.ContainerTrack.prototype.drawTrack.call(this, type);
    },

    drawFlowArrows_: function(viewLWorld, viewRWorld) {
      var ctx = this.context();
      var dt = this.viewport.currentDisplayTransform;
      dt.applyTransformToCanvas(ctx);

      var pixWidth = dt.xViewVectorToWorld(1);

      ctx.strokeStyle = 'rgba(0, 0, 0, 0.4)';
      ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
      ctx.lineWidth = pixWidth > 1.0 ? 1 : pixWidth;

      var events =
          this.model_.flowIntervalTree.findIntersection(viewLWorld, viewRWorld);

      var minWidth = 2 * pixWidth;
      var canvasBounds = ctx.canvas.getBoundingClientRect();

      for (var i = 0; i < events.length; ++i) {
        var startEvent = events[i][0];
        var endEvent = events[i][1];

        // Skip lines that will be, essentially, vertical.
        var distance = endEvent.start - startEvent.start;
        if (distance <= minWidth)
          continue;

        this.drawFlowArrowBetween_(
            ctx, startEvent, endEvent, canvasBounds, pixWidth);
      }
    },

    drawFlowArrowBetween_: function(ctx, startEvent, endEvent,
                                    canvasBounds, pixWidth) {
      var pixelRatio = window.devicePixelRatio || 1;

      var startTrack = this.viewport.trackForEvent(startEvent);
      var endTrack = this.viewport.trackForEvent(endEvent);

      var startBounds = startTrack.getBoundingClientRect();
      var endBounds = endTrack.getBoundingClientRect();

      var startSize = startBounds.left + startBounds.top +
          startBounds.bottom + startBounds.right;
      var endSize = endBounds.left + endBounds.top +
          endBounds.bottom + endBounds.right;
      // Nothing to do if both ends of the track are collapsed.
      if (startSize === 0 && endSize === 0)
        return;

      var startY = this.calculateTrackY_(startTrack, canvasBounds);
      var endY = this.calculateTrackY_(endTrack, canvasBounds);

      var pixelStartY = pixelRatio * startY;
      var pixelEndY = pixelRatio * endY;
      var half = (endEvent.start - startEvent.start) / 2;

      ctx.beginPath();
      ctx.moveTo(startEvent.start, pixelStartY);
      ctx.bezierCurveTo(
          startEvent.start + half, pixelStartY,
          startEvent.start + half, pixelEndY,
          endEvent.start, pixelEndY);
      ctx.stroke();

      var arrowWidth = 5 * pixWidth * pixelRatio;
      var distance = endEvent.start - startEvent.start;
      if (distance <= (2 * arrowWidth))
        return;

      var tipX = endEvent.start;
      var tipY = pixelEndY;
      var arrowHeight = (endBounds.height / 4) * pixelRatio;
      tracing.drawTriangle(ctx,
          tipX, tipY,
          tipX - arrowWidth, tipY - arrowHeight,
          tipX - arrowWidth, tipY + arrowHeight);
      ctx.fill();
    },

    calculateTrackY_: function(track, canvasBounds) {
      var bounds = track.getBoundingClientRect();
      var size = bounds.left + bounds.top + bounds.bottom + bounds.right;
      if (size === 0)
        return this.calculateTrackY_(track.parentNode, canvasBounds);

      return bounds.top - canvasBounds.top + (bounds.height / 2);
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      function onPickHit(instantEvent) {
        selection.push(instantEvent);
      }
      tvcm.iterateOverIntersectingIntervals(this.model_.instantEvents,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          loWX, hiWX,
          onPickHit.bind(this));

      tracing.tracks.ContainerTrack.prototype.
          addIntersectingItemsInRangeToSelectionInWorldSpace.
          apply(this, arguments);
    },

    addClosestEventToSelection: function(worldX, worldMaxDist, loY, hiY,
                                         selection) {
      this.addClosestInstantEventToSelection(this.model_.instantEvents,
                                             worldX, worldMaxDist, selection);
      tracing.tracks.ContainerTrack.prototype.addClosestEventToSelection.
          apply(this, arguments);
    }
  };

  return {
    TraceModelTrack: TraceModelTrack
  };
});
