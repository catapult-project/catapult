// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracks.timeline_counter_track');

base.require('tracks.timeline_canvas_based_track');
base.require('timeline_color_scheme');
base.require('ui');

base.exportTo('tracks', function() {

  var palette = tracing.getColorPalette();

  /**
   * A track that displays a TimelineCounter object.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineCounterTrack = base.ui.define(tracks.TimelineCanvasBasedTrack);

  TimelineCounterTrack.prototype = {

    __proto__: tracks.TimelineCanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-counter-track');
      this.addControlButtonElements_(false);
      this.selectedSamples_ = {};
      this.categoryFilter_ = new tracing.TimelineFilter();
    },

    /**
     * Called by all the addToSelection functions on the created selection
     * hit objects. Override this function on parent classes to add
     * context-specific information to the hit.
     */
    decorateHit: function(hit) {
    },

    get counter() {
      return this.counter_;
    },

    set counter(counter) {
      this.counter_ = counter;
      this.invalidate();
      this.updateVisibility_();
    },

    set categoryFilter(v) {
      this.categoryFilter_ = v;
      this.updateVisibility_();
    },

    /**
     * @return {Object} A sparse, mutable map from sample index to bool. Samples
     * indices the map that are true are drawn as selected. Callers that mutate
     * the map must manually call invalidate on the track to trigger a redraw.
     */
    get selectedSamples() {
      return this.selectedSamples_;
    },

    updateVisibility_: function() {
      this.visible = (this.counter_ &&
                      this.categoryFilter_.matchCounter(this.counter_));
    },

    redraw: function() {
      var ctr = this.counter_;
      var ctx = this.ctx_;
      var canvasW = this.canvas_.width;
      var canvasH = this.canvas_.height;

      ctx.clearRect(0, 0, canvasW, canvasH);

      // Culling parametrs.
      var vp = this.viewport_;
      var pixWidth = vp.xViewVectorToWorld(1);
      var viewLWorld = vp.xViewToWorld(0);
      var viewRWorld = vp.xViewToWorld(canvasW);

      // Give the viewport a chance to draw onto this canvas.
      vp.drawUnderContent(ctx, viewLWorld, viewRWorld, canvasH);

      // Drop sampels that are less than skipDistancePix apart.
      var skipDistancePix = 1;
      var skipDistanceWorld = vp.xViewVectorToWorld(skipDistancePix);

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanvas(ctx);

      // Figure out where drawing should begin.
      var numSeries = ctr.numSeries;
      var numSamples = ctr.numSamples;
      var startIndex = tracing.findLowIndexInSortedArray(ctr.timestamps,
                                                         function(x) {
                                                           return x;
                                                         },
                                                         viewLWorld);
      startIndex = startIndex - 1 > 0 ? startIndex - 1 : 0;

      // Draw indices one by one until we fall off the viewRWorld.
      var yScale = canvasH / ctr.maxTotal;
      for (var seriesIndex = ctr.numSeries - 1;
           seriesIndex >= 0; seriesIndex--) {
        var colorId = ctr.seriesColors[seriesIndex];
        ctx.fillStyle = palette[colorId];
        ctx.beginPath();

        // Set iLast and xLast such that the first sample we draw is the
        // startIndex sample.
        var iLast = startIndex - 1;
        var xLast = iLast >= 0 ? ctr.timestamps[iLast] - skipDistanceWorld : -1;
        var yLastView = canvasH;

        // Iterate over samples from iLast onward until we either fall off the
        // viewRWorld or we run out of samples. To avoid drawing too much, after
        // drawing a sample at xLast, skip subsequent samples that are less than
        // skipDistanceWorld from xLast.
        var hasMoved = false;
        while (true) {
          var i = iLast + 1;
          if (i >= numSamples) {
            ctx.lineTo(xLast, yLastView);
            ctx.lineTo(xLast + 8 * pixWidth, yLastView);
            ctx.lineTo(xLast + 8 * pixWidth, canvasH);
            break;
          }

          var x = ctr.timestamps[i];

          var y = ctr.totals[i * numSeries + seriesIndex];
          var yView = canvasH - (yScale * y);

          if (x > viewRWorld) {
            ctx.lineTo(x, yLastView);
            ctx.lineTo(x, canvasH);
            break;
          }

          if (x - xLast < skipDistanceWorld) {
            iLast = i;
            continue;
          }

          if (!hasMoved) {
            ctx.moveTo(viewLWorld, canvasH);
            hasMoved = true;
          }
          ctx.lineTo(x, yLastView);
          ctx.lineTo(x, yView);
          iLast = i;
          xLast = x;
          yLastView = yView;
        }
        ctx.closePath();
        ctx.fill();
      }
      ctx.fillStyle = 'rgba(255, 0, 0, 1)';
      for (var i in this.selectedSamples_) {
        if (!this.selectedSamples_[i])
          continue;

        var x = ctr.timestamps[i];
        for (var seriesIndex = ctr.numSeries - 1;
             seriesIndex >= 0; seriesIndex--) {
          var y = ctr.totals[i * numSeries + seriesIndex];
          var yView = canvasH - (yScale * y);
          ctx.fillRect(x - pixWidth, yView - 1, 3 * pixWidth, 3);
        }
      }
      ctx.restore();

      // Give the viewport a chance to draw over this canvas.
      vp.drawOverContent(ctx, viewLWorld, viewRWorld, canvasH);
    },

    /**
     * Adds items intersecting a point to a selection.
     * @param {number} vX X location to search at, in viewspace.
     * @param {number} vY Y location to search at, in viewspace.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(vX, vY, selection) {
      var clientRect = this.getBoundingClientRect();
      if (vY < clientRect.top || vY >= clientRect.bottom)
        return false;

      var pixelRatio = window.devicePixelRatio || 1;
      var wX = this.viewport_.xViewVectorToWorld(vX * devicePixelRatio);

      var ctr = this.counter_;
      if (vX < this.counter_.timestamps[0])
        return false;
      var i = tracing.findLowIndexInSortedArray(ctr.timestamps,
                                                function(x) { return x; },
                                                wX);
      if (i < 0 || i >= ctr.timestamps.length)
        return false;

      // Sample i is going to either be exactly at wX or slightly above it,
      // E.g. asking for 7.5 in [7,8] gives i=1. So bump i back by 1 if needed.
      if (i > 0 && wX > this.counter_.timestamps[i - 1])
        i--;

      // Some preliminaries.
      var canvasH = this.getBoundingClientRect().height;
      var yScale = canvasH / ctr.maxTotal;

      /*
      // Figure out which sample we hit
      var seriesIndexHit;
      for (var seriesIndex = 0; seriesIndex < ctr.numSeries; seriesIndex++) {
        var y = ctr.totals[i * ctr.numSeries + seriesIndex];
        var yView = canvasH - (yScale * y) + clientRect.top;
        if (wY >= yView) {
          seriesIndexHit = seriesIndex;
          break;
        }
      }
      if (seriesIndexHit === undefined)
        return false;
      */
      var hit = selection.addCounterSample(this, this.counter, i);
      this.decorateHit(hit);
      return true;
    },

    /**
     * Adds items intersecting the given range to a selection.
     * @param {number} loVX Lower X bound of the interval to search, in
     *     viewspace.
     * @param {number} hiVX Upper X bound of the interval to search, in
     *     viewspace.
     * @param {number} loVY Lower Y bound of the interval to search, in
     *     viewspace.
     * @param {number} hiVY Upper Y bound of the interval to search, in
     *     viewspace.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loVY, hiVY, selection) {

      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loVY, clientRect.top);
      var b = Math.min(hiVY, clientRect.bottom);
      if (a > b)
        return;

      var ctr = this.counter_;

      var pixelRatio = window.devicePixelRatio || 1;
      var loWX = this.viewport_.xViewToWorld(loVX * pixelRatio);
      var hiWX = this.viewport_.xViewToWorld(hiVX * pixelRatio);

      var iLo = tracing.findLowIndexInSortedArray(ctr.timestamps,
                                                  function(x) { return x; },
                                                  loWX);
      var iHi = tracing.findLowIndexInSortedArray(ctr.timestamps,
                                                  function(x) { return x; },
                                                  hiWX);

      // Sample i is going to either be exactly at wX or slightly above it,
      // E.g. asking for 7.5 in [7,8] gives i=1. So bump i back by 1 if needed.
      if (iLo > 0 && loWX > ctr.timestamps[iLo - 1])
        iLo--;
      if (iHi > 0 && hiWX > ctr.timestamps[iHi - 1])
        iHi--;

      // Iterate over every sample intersecting..
      for (var i = iLo; i <= iHi; i++) {
        if (i >= ctr.timestamps.length)
          continue;

        // TODO(nduca): Pick the seriesIndexHit based on the loY - hiY values.
        var hit = selection.addCounterSample(this, this.counter, i);
        this.decorateHit(hit);
      }
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    }
  };

  return {
    TimelineCounterTrack: TimelineCounterTrack
  };
});
