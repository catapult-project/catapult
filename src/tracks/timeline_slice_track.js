// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracks.timeline_slice_track');

base.require('tracks.timeline_canvas_based_track');
base.require('sorted_array_utils');
base.require('fast_rect_renderer');
base.require('timeline_color_scheme');
base.require('ui');

base.exportTo('tracks', function() {

  var palette = tracing.getColorPalette();

  /**
   * A track that displays an array of TimelineSlice objects.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineSliceTrack = base.ui.define(tracks.TimelineCanvasBasedTrack);

  TimelineSliceTrack.prototype = {

    __proto__: tracks.TimelineCanvasBasedTrack.prototype,

    /**
     * Should we elide text on trace labels?
     * Without eliding, text that is too wide isn't drawn at all.
     * Disable if you feel this causes a performance problem.
     * This is a default value that can be overridden in tracks for testing.
     * @const
     */
    SHOULD_ELIDE_TEXT: true,

    decorate: function() {
      this.classList.add('timeline-slice-track');
      this.elidedTitleCache = new ElidedTitleCache();
      this.asyncStyle_ = false;
    },

    /**
     * Called by all the addToSelection functions on the created selection
     * hit objects. Override this function on parent classes to add
     * context-specific information to the hit.
     */
    decorateHit: function(hit) {
    },

    get asyncStyle() {
      return this.asyncStyle_;
    },

    set asyncStyle(v) {
      this.asyncStyle_ = !!v;
      this.invalidate();
    },

    get slices() {
      return this.slices_;
    },

    set slices(slices) {
      this.slices_ = slices || [];
      if (!slices)
        this.visible = false;
      this.invalidate();
    },

    get height() {
      return window.getComputedStyle(this).height;
    },

    set height(height) {
      this.style.height = height;
      this.invalidate();
    },

    labelWidth: function(title) {
      return quickMeasureText(this.ctx_, title) + 2;
    },

    labelWidthWorld: function(title, pixWidth) {
      return this.labelWidth(title) * pixWidth;
    },

    redraw: function() {
      var ctx = this.ctx_;
      var canvasW = this.canvas_.width;
      var canvasH = this.canvas_.height;

      ctx.clearRect(0, 0, canvasW, canvasH);

      // Culling parameters.
      var vp = this.viewport_;
      var pixWidth = vp.xViewVectorToWorld(1);
      var viewLWorld = vp.xViewToWorld(0);
      var viewRWorld = vp.xViewToWorld(canvasW);

      // Give the viewport a chance to draw onto this canvas.
      vp.drawUnderContent(ctx, viewLWorld, viewRWorld, canvasH);

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanvas(ctx);

      // Slices.
      if (this.asyncStyle_)
        ctx.globalAlpha = 0.25;
      var tr = new tracing.FastRectRenderer(ctx, 2 * pixWidth, 2 * pixWidth,
                                            palette);
      tr.setYandH(0, canvasH);
      var slices = this.slices_;
      var lowSlice = tracing.findLowIndexInSortedArray(slices,
                                                       function(slice) {
                                                         return slice.start +
                                                                slice.duration;
                                                       },
                                                       viewLWorld);
      for (var i = lowSlice; i < slices.length; ++i) {
        var slice = slices[i];
        var x = slice.start;
        if (x > viewRWorld) {
          break;
        }
        // Less than 0.001 causes short events to disappear when zoomed in.
        var w = Math.max(slice.duration, 0.001);
        var colorId = slice.selected ?
            slice.colorId + highlightIdBoost :
            slice.colorId;

        if (w < pixWidth)
          w = pixWidth;
        if (slice.duration > 0) {
          tr.fillRect(x, w, colorId);
        } else {
          // Instant: draw a triangle.  If zoomed too far, collapse
          // into the FastRectRenderer.
          if (pixWidth > 0.001) {
            tr.fillRect(x, pixWidth, colorId);
          } else {
            ctx.fillStyle = palette[colorId];
            ctx.beginPath();
            ctx.moveTo(x - (4 * pixWidth), canvasH);
            ctx.lineTo(x, 0);
            ctx.lineTo(x + (4 * pixWidth), canvasH);
            ctx.closePath();
            ctx.fill();
          }
        }
      }
      tr.flush();
      ctx.restore();

      // Labels.
      var pixelRatio = window.devicePixelRatio || 1;
      if (canvasH > 8) {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.font = (10 * pixelRatio) + 'px sans-serif';
        ctx.strokeStyle = 'rgb(0,0,0)';
        ctx.fillStyle = 'rgb(0,0,0)';
        // Don't render text until until it is 20px wide
        var quickDiscardThresshold = pixWidth * 20;
        var shouldElide = this.SHOULD_ELIDE_TEXT;
        for (var i = lowSlice; i < slices.length; ++i) {
          var slice = slices[i];
          if (slice.start > viewRWorld) {
            break;
          }
          if (slice.duration > quickDiscardThresshold) {
            var title = slice.title;
            if (slice.didNotFinish) {
              title += ' (Did Not Finish)';
            }
            var drawnTitle = title;
            var drawnWidth = this.labelWidth(drawnTitle);
            if (shouldElide &&
                this.labelWidthWorld(drawnTitle, pixWidth) > slice.duration) {
              var elidedValues = this.elidedTitleCache.get(
                  this, pixWidth,
                  drawnTitle, drawnWidth,
                  slice.duration);
              drawnTitle = elidedValues.string;
              drawnWidth = elidedValues.width;
            }
            if (drawnWidth * pixWidth < slice.duration) {
              var cX = vp.xWorldToView(slice.start + 0.5 * slice.duration);
              ctx.fillText(drawnTitle, cX, 2.5 * pixelRatio, drawnWidth);
            }
          }
        }
      }

      // Give the viewport a chance to draw over this canvas.
      vp.drawOverContent(ctx, viewLWorld, viewRWorld, canvasH);
    },

    /**
     * Finds slices intersecting the given interval.
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
      var x = tracing.findLowIndexInSortedIntervals(this.slices_,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          wX);
      if (x >= 0 && x < this.slices_.length) {
        var hit = selection.addSlice(this, this.slices_[x]);
        this.decorateHit(hit);
        return true;
      }
      return false;
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

      var pixelRatio = window.devicePixelRatio || 1;
      var loWX = this.viewport_.xViewToWorld(loVX * pixelRatio);
      var hiWX = this.viewport_.xViewToWorld(hiVX * pixelRatio);

      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loVY, clientRect.top);
      var b = Math.min(hiVY, clientRect.bottom);
      if (a > b)
        return;

      var that = this;
      function onPickHit(slice) {
        var hit = selection.addSlice(that, slice);
        that.decorateHit(hit);
      }
      tracing.iterateOverIntersectingIntervals(this.slices_,
          function(x) { return x.start; },
          function(x) { return x.duration; },
          loWX, hiWX,
          onPickHit);
    },

    /**
     * Find the index for the given slice.
     * @return {index} Index of the given slice, or undefined.
     * @private
     */
    indexOfSlice_: function(slice) {
      var index = tracing.findLowIndexInSortedArray(this.slices_,
          function(x) { return x.start; },
          slice.start);
      while (index < this.slices_.length &&
          slice.start == this.slices_[index].start &&
          slice.colorId != this.slices_[index].colorId) {
        index++;
      }
      return index < this.slices_.length ? index : undefined;
    },

    /**
     * Add the item to the left or right of the provided hit, if any, to the
     * selection.
     * @param {slice} The current slice.
     * @param {Number} offset Number of slices away from the hit to look.
     * @param {TimelineSelection} selection The selection to add a hit to,
     * if found.
     * @return {boolean} Whether a hit was found.
     * @private
     */
    addItemNearToProvidedHitToSelection: function(hit, offset, selection) {
      if (!hit.slice)
        return false;

      var index = this.indexOfSlice_(hit.slice);
      if (index === undefined)
        return false;

      var newIndex = index + offset;
      if (newIndex < 0 || newIndex >= this.slices_.length)
        return false;

      var hit = selection.addSlice(this, this.slices_[newIndex]);
      this.decorateHit(hit);
      return true;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.slices_.length; ++i) {
        if (filter.matchSlice(this.slices_[i])) {
          var hit = selection.addSlice(this, this.slices_[i]);
          this.decorateHit(hit);
        }
      }
    }
  };

  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  // TODO(jrg): possibly obsoleted with the elided string cache.
  // Consider removing.
  var textWidthMap = { };
  function quickMeasureText(ctx, text) {
    var w = textWidthMap[text];
    if (!w) {
      w = ctx.measureText(text).width;
      textWidthMap[text] = w;
    }
    return w;
  }

  /**
   * Cache for elided strings.
   * Moved from the ElidedTitleCache protoype to a "global" for speed
   * (variable reference is 100x faster).
   *   key: String we wish to elide.
   *   value: Another dict whose key is width
   *     and value is an ElidedStringWidthPair.
   */
  var elidedTitleCacheDict = {};

  /**
   * A cache for elided strings.
   * @constructor
   */
  function ElidedTitleCache() {
  }

  ElidedTitleCache.prototype = {
    /**
     * Return elided text.
     * @param {track} A timeline slice track or other object that defines
     *                functions labelWidth() and labelWidthWorld().
     * @param {pixWidth} Pixel width.
     * @param {title} Original title text.
     * @param {width} Drawn width in world coords.
     * @param {sliceDuration} Where the title must fit (in world coords).
     * @return {ElidedStringWidthPair} Elided string and width.
     */
    get: function(track, pixWidth, title, width, sliceDuration) {
      var elidedDict = elidedTitleCacheDict[title];
      if (!elidedDict) {
        elidedDict = {};
        elidedTitleCacheDict[title] = elidedDict;
      }
      var elidedDictForPixWidth = elidedDict[pixWidth];
      if (!elidedDictForPixWidth) {
        elidedDict[pixWidth] = {};
        elidedDictForPixWidth = elidedDict[pixWidth];
      }
      var stringWidthPair = elidedDictForPixWidth[sliceDuration];
      if (stringWidthPair === undefined) {
        var newtitle = title;
        var elided = false;
        while (track.labelWidthWorld(newtitle, pixWidth) > sliceDuration) {
          newtitle = newtitle.substring(0, newtitle.length * 0.75);
          elided = true;
        }
        if (elided && newtitle.length > 3)
          newtitle = newtitle.substring(0, newtitle.length - 3) + '...';
        stringWidthPair = new ElidedStringWidthPair(
            newtitle,
            track.labelWidth(newtitle));
        elidedDictForPixWidth[sliceDuration] = stringWidthPair;
      }
      return stringWidthPair;
    }
  };

  /**
   * A pair representing an elided string and world-coordinate width
   * to draw it.
   * @constructor
   */
  function ElidedStringWidthPair(string, width) {
    this.string = string;
    this.width = width;
  }

  return {
    TimelineSliceTrack: TimelineSliceTrack
  };
});
