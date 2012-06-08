// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */
cr.define('tracing', function() {

  var pallette = tracing.getPallette();
  var highlightIdBoost = tracing.getPalletteHighlightIdBoost();

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
   * A generic track that contains other tracks as its children.
   * @constructor
   */
  var TimelineContainerTrack = cr.ui.define('div');
  TimelineContainerTrack.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.tracks_ = [];
    },

    detach: function() {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].detach();
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(v) {
      this.viewport_ = v;
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].viewport = v;
      this.updateChildTracks_();
    },

    get firstCanvas() {
      if (this.tracks_.length)
        return this.tracks_[0].firstCanvas;
      return undefined;
    },

    /**
     * Adds items intersecting a point to a selection.
     * @param {number} wX X location to search at, in worldspace.
     * @param {number} wY Y location to search at, in offset space.
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(wX, wY, selection) {
      for (var i = 0; i < this.tracks_.length; i++) {
        var trackClientRect = this.tracks_[i].getBoundingClientRect();
        if (wY >= trackClientRect.top && wY < trackClientRect.bottom)
          this.tracks_[i].addIntersectingItemsToSelection(wX, wY, selection);
      }
      return false;
    },

    /**
     * Adds items intersecting the given range to a selection.
     * @param {number} loWX Lower X bound of the interval to search, in
     *     worldspace.
     * @param {number} hiWX Upper X bound of the interval to search, in
     *     worldspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     offset space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loWX, hiWX, loY, hiY, selection) {
      for (var i = 0; i < this.tracks_.length; i++) {
        var trackClientRect = this.tracks_[i].getBoundingClientRect();
        var a = Math.max(loY, trackClientRect.top);
        var b = Math.min(hiY, trackClientRect.bottom);
        if (a <= b)
          this.tracks_[i].addIntersectingItemsInRangeToSelection(
              loWX, hiWX, loY, hiY, selection);
      }
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
      for (var i = 0; i < this.tracks_.length; i++)
        this.tracks_[i].addAllObjectsMatchingFilterToSelection(
          filter, selection);
    }
  };

  function addControlButtonElements(el, canCollapse) {
    var closeEl = document.createElement('div');
    closeEl.classList.add('timeline-track-button');
    closeEl.classList.add('timeline-track-close-button');
    closeEl.textContent = String.fromCharCode(215); // &times;
    closeEl.addEventListener('click', function() {
      el.style.display = 'None';
    });
    el.appendChild(closeEl);

    if (canCollapse) {
      var collapseEl = document.createElement('div');
      collapseEl.classList.add('timeline-track-button');
      collapseEl.classList.add('timeline-track-collapse-button');
      var minus = '\u2212'; // minus sign;
      var plus = '\u002b'; // plus sign;
      collapseEl.textContent = minus;
      var collapsed = false;
      collapseEl.addEventListener('click', function() {
        collapsed = !collapsed;
        el.collapsedDidChange(collapsed);
        collapseEl.textContent = collapsed ? plus : minus;
      });
      el.appendChild(collapseEl);
    }
  }

  /**
   * Visualizes a TimelineThread using a series of of TimelineSliceTracks.
   * @constructor
   */
  var TimelineThreadTrack = cr.ui.define(TimelineContainerTrack);
  TimelineThreadTrack.prototype = {
    __proto__: TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-thread-track');
    },

    get thread() {
      return this.thread_;
    },

    set thread(thread) {
      this.thread_ = thread;
      this.updateChildTracks_();
    },

    get tooltip() {
      return this.tooltip_;
    },

    set tooltip(value) {
      this.tooltip_ = value;
      this.updateChildTracks_();
    },

    get heading() {
      return this.heading_;
    },

    set heading(h) {
      this.heading_ = h;
      this.updateChildTracks_();
    },

    get headingWidth() {
      return this.headingWidth_;
    },

    set headingWidth(width) {
      this.headingWidth_ = width;
      this.updateChildTracks_();
    },

    addTrack_: function(slices) {
      var track = new TimelineSliceTrack();
      track.heading = '';
      track.slices = slices;
      track.headingWidth = this.headingWidth_;
      track.viewport = this.viewport_;

      this.tracks_.push(track);
      this.appendChild(track);
      return track;
    },

    updateChildTracks_: function() {
      this.detach();
      this.textContent = '';
      this.tracks_ = [];
      if (this.thread_) {
        if (this.thread_.cpuSlices) {
          var track = this.addTrack_(this.thread_.cpuSlices);
          track.height = '4px';
          track.decorateHit = function(hit) {
            hit.thread = this.thread_;
          }
        }

        if (this.thread_.asyncSlices.length) {
          var subRows = this.thread_.asyncSlices.subRows;
          for (var srI = 0; srI < subRows.length; srI++) {
            var track = this.addTrack_(subRows[srI]);
            track.decorateHit = function(hit) {
              // TODO(simonjam): figure out how to associate subSlice hits back
              // to their parent slice.
            }
            track.asyncStyle = true;
          }
        }

        for (var srI = 0; srI < this.thread_.subRows.length; srI++) {
          var track = this.addTrack_(this.thread_.subRows[srI]);
          track.decorateHit = function(hit) {
            hit.thread = this.thread_;
          }
        }

        if (this.tracks_.length > 0) {
          if (this.thread_.cpuSlices) {
            this.tracks_[1].heading = this.heading_;
            this.tracks_[1].tooltip = this.tooltip_;
          } else {
            this.tracks_[0].heading = this.heading_;
            this.tracks_[0].tooltip = this.tooltip_;
          }
        }
      }
      addControlButtonElements(this, this.tracks_.length >= 4);
    },

    collapsedDidChange: function(collapsed) {
      if (collapsed) {
        var h = parseInt(this.tracks_[0].height);
        for (var i = 0; i < this.tracks_.length; ++i) {
          if (h > 2) {
            this.tracks_[i].height = Math.floor(h) + 'px';
          } else {
            this.tracks_[i].style.display = 'None';
          }
          h = h * 0.5;
        }
      } else {
        for (var i = 0; i < this.tracks_.length; ++i) {
          this.tracks_[i].height = this.tracks_[0].height;
          this.tracks_[i].style.display = '';
        }
      }
    }
  };

  /**
   * Visualizes a TimelineCpu using a series of of TimelineSliceTracks.
   * @constructor
   */
  var TimelineCpuTrack = cr.ui.define(TimelineContainerTrack);
  TimelineCpuTrack.prototype = {
    __proto__: TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-thread-track');
    },

    get cpu() {
      return this.cpu_;
    },

    set cpu(cpu) {
      this.cpu_ = cpu;
      this.updateChildTracks_();
    },

    get tooltip() {
      return this.tooltip_;
    },

    set tooltip(value) {
      this.tooltip_ = value;
      this.updateChildTracks_();
    },

    get heading() {
      return this.heading_;
    },

    set heading(h) {
      this.heading_ = h;
      this.updateChildTracks_();
    },

    get headingWidth() {
      return this.headingWidth_;
    },

    set headingWidth(width) {
      this.headingWidth_ = width;
      this.updateChildTracks_();
    },

    updateChildTracks_: function() {
      this.detach();
      this.textContent = '';
      this.tracks_ = [];
      if (this.cpu_) {
        var track = new TimelineSliceTrack();
        track.slices = this.cpu_.slices;
        track.headingWidth = this.headingWidth_;
        track.viewport = this.viewport_;

        this.tracks_.push(track);
        this.appendChild(track);

        this.tracks_[0].heading = this.heading_;
        this.tracks_[0].tooltip = this.tooltip_;
      }
      addControlButtonElements(this, false);
    }
  };

  /**
   * A canvas-based track constructed. Provides the basic heading and
   * invalidation-managment infrastructure. Subclasses must implement drawing
   * and picking code.
   * @constructor
   * @extends {HTMLDivElement}
   */
  var CanvasBasedTrack = cr.ui.define('div');

  CanvasBasedTrack.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'timeline-canvas-based-track';
      this.slices_ = null;

      this.headingDiv_ = document.createElement('div');
      this.headingDiv_.className = 'timeline-canvas-based-track-title';
      this.appendChild(this.headingDiv_);

      this.canvasContainer_ = document.createElement('div');
      this.canvasContainer_.className =
          'timeline-canvas-based-track-canvas-container';
      this.appendChild(this.canvasContainer_);
      this.canvas_ = document.createElement('canvas');
      this.canvas_.className = 'timeline-canvas-based-track-canvas';
      this.canvasContainer_.appendChild(this.canvas_);

      this.ctx_ = this.canvas_.getContext('2d');
    },

    detach: function() {
      if (this.viewport_)
        this.viewport_.removeEventListener('change',
                                           this.viewportChangeBoundToThis_);
    },

    set headingWidth(width) {
      this.headingDiv_.style.width = width;
    },

    get heading() {
      return this.headingDiv_.textContent;
    },

    set heading(text) {
      this.headingDiv_.textContent = text;
    },

    set tooltip(text) {
      this.headingDiv_.title = text;
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(v) {
      this.viewport_ = v;
      if (this.viewport_)
        this.viewport_.removeEventListener('change',
                                           this.viewportChangeBoundToThis_);
      this.viewport_ = v;
      if (this.viewport_) {
        this.viewportChangeBoundToThis_ = this.viewportChange_.bind(this);
        this.viewport_.addEventListener('change',
                                        this.viewportChangeBoundToThis_);
      }
      this.invalidate();
    },

    viewportChange_: function() {
      this.invalidate();
    },

    invalidate: function() {
      if (this.rafPending_)
        return;
      webkitRequestAnimationFrame(function() {
        this.rafPending_ = false;
        if (!this.viewport_)
          return;

        var style = window.getComputedStyle(this.canvasContainer_);
        var style_width = parseInt(style.width);
        var style_height = parseInt(style.height);
        if (this.canvas_.width != style_width)
          this.canvas_.width = style_width;
        if (this.canvas_.height != style_height)
          this.canvas_.height = style_height;

        this.redraw();
      }.bind(this), this);
      this.rafPending_ = true;
    },

    get firstCanvas() {
      return this.canvas_;
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
   * A track that displays an array of TimelineSlice objects.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineSliceTrack = cr.ui.define(CanvasBasedTrack);

  TimelineSliceTrack.prototype = {

    __proto__: CanvasBasedTrack.prototype,

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
      this.slices_ = slices;
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

      // Draw grid without a transform because the scale
      // affects line width.
      if (vp.gridEnabled) {
        var x = vp.gridTimebase;
        ctx.beginPath();
        while (x < viewRWorld) {
          if (x >= viewLWorld) {
            // Do conversion to viewspace here rather than on
            // x to avoid precision issues.
            var vx = vp.xWorldToView(x);
            ctx.moveTo(vx, 0);
            ctx.lineTo(vx, canvasH);
          }
          x += vp.gridStep;
        }
        ctx.strokeStyle = 'rgba(255,0,0,0.25)';
        ctx.stroke();
      }

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanavs(ctx);

      // Slices.
      if (this.asyncStyle_)
        ctx.globalAlpha = 0.25;
      var tr = new tracing.FastRectRenderer(ctx, viewLWorld, 2 * pixWidth,
                                            2 * pixWidth, viewRWorld, pallette);
      tr.setYandH(0, canvasH);
      var slices = this.slices_;
      for (var i = 0; i < slices.length; ++i) {
        var slice = slices[i];
        var x = slice.start;
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
            ctx.fillStyle = pallette[colorId];
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
      if (canvasH > 8) {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.font = '10px sans-serif';
        ctx.strokeStyle = 'rgb(0,0,0)';
        ctx.fillStyle = 'rgb(0,0,0)';
        // Don't render text until until it is 20px wide
        var quickDiscardThresshold = pixWidth * 20;
        var shouldElide = this.SHOULD_ELIDE_TEXT;
        for (var i = 0; i < slices.length; ++i) {
          var slice = slices[i];
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
              ctx.fillText(drawnTitle, cX, 2.5, drawnWidth);
            }
          }
        }
      }
    },

    /**
     * Finds slices intersecting the given interval.
     * @param {number} wX X location to search at, in worldspace.
     * @param {number} wY Y location to search at, in offset space.
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(wX, wY, selection) {
      var clientRect = this.getBoundingClientRect();
      if (wY < clientRect.top || wY >= clientRect.bottom)
        return false;
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
     * @param {number} loWX Lower X bound of the interval to search, in
     *     worldspace.
     * @param {number} hiWX Upper X bound of the interval to search, in
     *     worldspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     offset space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loWX, hiWX, loY, hiY, selection) {
      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loY, clientRect.top);
      var b = Math.min(hiY, clientRect.bottom);
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

  /**
   * A track that displays the viewport size and scale.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineViewportTrack = cr.ui.define(CanvasBasedTrack);

  var logOf10 = Math.log(10);
  function log10(x) {
    return Math.log(x) / logOf10;
  }

  TimelineViewportTrack.prototype = {

    __proto__: CanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-viewport-track');
      this.strings_secs_ = [];
      this.strings_msecs_ = [];
    },

    redraw: function() {
      var ctx = this.ctx_;
      var canvasW = this.canvas_.width;
      var canvasH = this.canvas_.height;

      ctx.clearRect(0, 0, canvasW, canvasH);

      // Culling parametrs.
      var vp = this.viewport_;
      var pixWidth = vp.xViewVectorToWorld(1);
      var viewLWorld = vp.xViewToWorld(0);
      var viewRWorld = vp.xViewToWorld(canvasW);

      var idealMajorMarkDistancePix = 150;
      var idealMajorMarkDistanceWorld =
          vp.xViewVectorToWorld(idealMajorMarkDistancePix);

      // The conservative guess is the nearest enclosing 0.1, 1, 10, 100, etc
      var conservativeGuess =
          Math.pow(10, Math.ceil(log10(idealMajorMarkDistanceWorld)));

      // Once we have a conservative guess, consider things that evenly add up
      // to the conservative guess, e.g. 0.5, 0.2, 0.1 Pick the one that still
      // exceeds the ideal mark distance.
      var divisors = [10, 5, 2, 1];
      for (var i = 0; i < divisors.length; ++i) {
        var tightenedGuess = conservativeGuess / divisors[i];
        if (vp.xWorldVectorToView(tightenedGuess) < idealMajorMarkDistancePix)
          continue;
        majorMarkDistanceWorld = conservativeGuess / divisors[i - 1];
        break;
      }
      var tickLabels = undefined;
      if (majorMarkDistanceWorld < 100) {
        unit = 'ms';
        unitDivisor = 1;
        tickLabels = this.strings_msecs_;
      } else {
        unit = 's';
        unitDivisor = 1000;
        tickLabels = this.strings_secs_;
      }

      var numTicksPerMajor = 5;
      var minorMarkDistanceWorld = majorMarkDistanceWorld / numTicksPerMajor;
      var minorMarkDistancePx = vp.xWorldVectorToView(minorMarkDistanceWorld);

      var firstMajorMark =
          Math.floor(viewLWorld / majorMarkDistanceWorld) *
              majorMarkDistanceWorld;

      var minorTickH = Math.floor(canvasH * 0.25);

      ctx.fillStyle = 'rgb(0, 0, 0)';
      ctx.strokeStyle = 'rgb(0, 0, 0)';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.font = '9px sans-serif';

      // Each iteration of this loop draws one major mark
      // and numTicksPerMajor minor ticks.
      //
      // Rendering can't be done in world space because canvas transforms
      // affect line width. So, do the conversions manually.
      for (var curX = firstMajorMark;
           curX < viewRWorld;
           curX += majorMarkDistanceWorld) {

        var curXView = Math.floor(vp.xWorldToView(curX));

        var unitValue = curX / unitDivisor;
        var roundedUnitValue = Math.floor(unitValue * 100000) / 100000;
        if (!tickLabels[roundedUnitValue])
            tickLabels[roundedUnitValue] = roundedUnitValue + ' ' + unit;
        ctx.fillText(tickLabels[roundedUnitValue], curXView + 2, 0);
        ctx.beginPath();

        // Major mark
        ctx.moveTo(curXView, 0);
        ctx.lineTo(curXView, canvasW);

        // Minor marks
        for (var i = 1; i < numTicksPerMajor; ++i) {
          var xView = Math.floor(curXView + minorMarkDistancePx * i);
          ctx.moveTo(xView, canvasH - minorTickH);
          ctx.lineTo(xView, canvasH);
        }

        ctx.stroke();
      }
    },

    /**
     * Adds items intersecting a point to a selection.
     * @param {number} wX X location to search at, in worldspace.
     * @param {number} wY Y location to search at, in offset space.
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(wX, wY, selection) {
      // Does nothing. There's nothing interesting to pick on the viewport
      // track.
    },

    /**
     * Adds items intersecting the given range to a selection.
     * @param {number} loWX Lower X bound of the interval to search, in
     *     worldspace.
     * @param {number} hiWX Upper X bound of the interval to search, in
     *     worldspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     offset space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loWX, hiWX, loY, hiY, selection) {
      // Does nothing. There's nothing interesting to pick on the viewport
      // track.
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    }

  };

  /**
   * A track that displays a TimelineCounter object.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineCounterTrack = cr.ui.define(CanvasBasedTrack);

  TimelineCounterTrack.prototype = {

    __proto__: CanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-counter-track');
      addControlButtonElements(this, false);
      this.selectedSamples_ = {};
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
    },

    /**
     * @return {Object} A sparce, mutable map from sample index to bool. Samples
     * indices the map that are true are drawn as selected. Callers that mutate
     * the map must manually call invalidate on the track to trigger a redraw.
     */
    get selectedSamples() {
      return this.selectedSamples_;
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

      // Drop sampels that are less than skipDistancePix apart.
      var skipDistancePix = 1;
      var skipDistanceWorld = vp.xViewVectorToWorld(skipDistancePix);

      // Begin rendering in world space.
      ctx.save();
      vp.applyTransformToCanavs(ctx);

      // Figure out where drawing should begin.
      var numSeries = ctr.numSeries;
      var numSamples = ctr.numSamples;
      var startIndex = tracing.findLowIndexInSortedArray(ctr.timestamps,
                                                         function() {
                                                         },
                                                         viewLWorld);

      // Draw indices one by one until we fall off the viewRWorld.
      var yScale = canvasH / ctr.maxTotal;
      for (var seriesIndex = ctr.numSeries - 1;
           seriesIndex >= 0; seriesIndex--) {
        var colorId = ctr.seriesColors[seriesIndex];
        ctx.fillStyle = pallette[colorId];
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
    },

    /**
     * Adds items intersecting a point to a selection.
     * @param {number} wX X location to search at, in worldspace.
     * @param {number} wY Y location to search at, in offset space.
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     * @return {boolean} true if a slice was found, otherwise false.
     */
    addIntersectingItemsToSelection: function(wX, wY, selection) {
      var clientRect = this.getBoundingClientRect();
      if (wY < clientRect.top || wY >= clientRect.bottom)
        return false;
      var ctr = this.counter_;
      if (wX < this.counter_.timestamps[0])
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
     * @param {number} loWX Lower X bound of the interval to search, in
     *     worldspace.
     * @param {number} hiWX Upper X bound of the interval to search, in
     *     worldspace.
     * @param {number} loY Lower Y bound of the interval to search, in
     *     offset space.
     * @param {number} hiY Upper Y bound of the interval to search, in
     *     offset space.
     * @param {TimelineSelection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
      loWX, hiWX, loY, hiY, selection) {

      var clientRect = this.getBoundingClientRect();
      var a = Math.max(loY, clientRect.top);
      var b = Math.min(hiY, clientRect.bottom);
      if (a > b)
        return;

      var ctr = this.counter_;

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
    TimelineCounterTrack: TimelineCounterTrack,
    TimelineSliceTrack: TimelineSliceTrack,
    TimelineThreadTrack: TimelineThreadTrack,
    TimelineViewportTrack: TimelineViewportTrack,
    TimelineCpuTrack: TimelineCpuTrack
  };
});
