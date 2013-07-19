// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.counter_track');

base.require('tracing.tracks.heading_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var palette = tracing.getColorPalette();

  /**
   * A track that displays a Counter object.
   * @constructor
   * @extends {HeadingTrack}
   */

  var CounterTrack =
      ui.define('counter-track', tracing.tracks.HeadingTrack);

  CounterTrack.prototype = {

    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('counter-track');
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
      this.heading = counter.name + ': ';
    },

    get categoryFilter() {
      return this.categoryFilter_;
    },

    set categoryFilter(v) {
      this.categoryFilter_ = v;
    },

    /**
     * @return {Object} A sparse, mutable map from sample index to bool. Samples
     * indices the map that are true are drawn as selected.
     */
    get selectedSamples() {
      return this.selectedSamples_;
    },

    draw: function(type, viewLWorld, viewRWorld) {
      switch (type) {
        case tracing.tracks.DrawType.SLICE:
          this.drawSlices_(viewLWorld, viewRWorld);
          break;
      }
    },

    drawSlices_: function(viewLWorld, viewRWorld) {
      var ctx = this.context();
      var pixelRatio = window.devicePixelRatio || 1;

      var bounds = this.getBoundingClientRect();
      var height = bounds.height * pixelRatio;

      var counter = this.counter_;

      // Culling parametrs.
      var vp = this.viewport;
      var pixWidth = vp.xViewVectorToWorld(1);

      // Drop sampels that are less than skipDistancePix apart.
      var skipDistancePix = 1;
      var skipDistanceWorld = vp.xViewVectorToWorld(skipDistancePix);

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanvas(ctx);

      // Figure out where drawing should begin.
      var numSeries = counter.numSeries;
      var numSamples = counter.numSamples;
      var startIndex = base.findLowIndexInSortedArray(
          counter.timestamps,
          function(x) { return x; },
          viewLWorld);

      startIndex = startIndex - 1 > 0 ? startIndex - 1 : 0;
      // Draw indices one by one until we fall off the viewRWorld.
      var yScale = height / counter.maxTotal;
      for (var seriesIndex = counter.numSeries - 1;
           seriesIndex >= 0; seriesIndex--) {
        var colorId = counter.series[seriesIndex].color;
        ctx.fillStyle = palette[colorId];
        ctx.beginPath();

        // Set iLast and xLast such that the first sample we draw is the
        // startIndex sample.
        var iLast = startIndex - 1;
        var xLast = iLast >= 0 ?
            counter.timestamps[iLast] - skipDistanceWorld : -1;
        var yLastView = height;

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
            ctx.lineTo(xLast + 8 * pixWidth, height);
            break;
          }

          var x = counter.timestamps[i];
          var y = counter.totals[i * numSeries + seriesIndex];
          var yView = height - (yScale * y);

          if (x > viewRWorld) {
            ctx.lineTo(x, yLastView);
            ctx.lineTo(x, height);
            break;
          }

          if (i + 1 < numSamples) {
            var xNext = counter.timestamps[i + 1];
            if (xNext - xLast <= skipDistanceWorld && xNext < viewRWorld) {
              iLast = i;
              continue;
            }
          }

          if (!hasMoved) {
            ctx.moveTo(viewLWorld, height);
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

        var x = counter.timestamps[i];
        for (var seriesIndex = counter.numSeries - 1;
             seriesIndex >= 0; seriesIndex--) {
          var y = counter.totals[i * numSeries + seriesIndex];
          var yView = height - (yScale * y);
          ctx.fillRect(x - pixWidth, yView - 1, 3 * pixWidth, 3);
        }
      }
      ctx.restore();
    },

    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {

      function getSampleWidth(x, i) {
        if (i === counter.timestamps.length - 1)
          return 0;
        return counter.timestamps[i + 1] - counter.timestamps[i];
      }

      var counter = this.counter_;
      var iLo = base.findLowIndexInSortedIntervals(counter.timestamps,
                                                   function(x) { return x; },
                                                   getSampleWidth,
                                                   loWX);
      var iHi = base.findLowIndexInSortedIntervals(counter.timestamps,
                                                   function(x) { return x; },
                                                   getSampleWidth,
                                                   hiWX);

      // Iterate over every sample intersecting..
      for (var i = iLo; i <= iHi; i++) {
        if (i < 0)
          continue;
        if (i >= counter.timestamps.length)
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
