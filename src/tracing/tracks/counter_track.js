// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.counter_track');

base.require('tracing.tracks.canvas_based_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var palette = tracing.getColorPalette();

  /**
   * A track that displays a Counter object.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var CounterTrack =
      ui.define('counter-track', tracing.tracks.CanvasBasedTrack);

  CounterTrack.prototype = {

    __proto__: tracing.tracks.CanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('counter-track');
      this.addControlButtonElements_(false);
      this.selectedSamples_ = {};
      this.categoryFilter_ = new tracing.Filter();
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
      var startIndex = base.findLowIndexInSortedArray(ctr.timestamps,
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

          if (i + 1 < numSamples) {
            var xNext = ctr.timestamps[i + 1];
            if (xNext - xLast <= skipDistanceWorld && xNext < viewRWorld) {
              iLast = i;
              continue;
            }
          }

          if (!hasMoved) {
            ctx.moveTo(viewLWorld, canvasH);
            hasMoved = true;
          }
          if (x - xLast < skipDistanceWorld) {
            // We know that xNext > xLast + skipDistanceWorld, so we can
            // safely move this sample's x over that much without passing
            // xNext.  This ensure that the previous sample is visible when
            // zoomed out very far.
            x = xLast + skipDistanceWorld;
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

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {

      function getSampleWidth(x, i) {
        if (i == ctr.timestamps.length - 1)
          return 0;
        return ctr.timestamps[i + 1] - ctr.timestamps[i];
      }

      var ctr = this.counter_;
      var iLo = base.findLowIndexInSortedIntervals(ctr.timestamps,
                                                   function(x) { return x; },
                                                   getSampleWidth,
                                                   loWX);
      var iHi = base.findLowIndexInSortedIntervals(ctr.timestamps,
                                                   function(x) { return x; },
                                                   getSampleWidth,
                                                   hiWX);

      // Iterate over every sample intersecting..
      for (var i = iLo; i <= iHi; i++) {
        if (i < 0)
          continue;
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
    CounterTrack: CounterTrack
  };
});
