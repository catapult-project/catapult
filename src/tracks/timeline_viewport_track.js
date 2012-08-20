// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Renders an array of slices into the provided div,
 * using a child canvas element. Uses a FastRectRenderer to draw only
 * the visible slices.
 */
base.defineModule('tracks.timeline_viewport_track')
    .dependsOn('tracks.timeline_track',
               'tracks.timeline_canvas_based_track',
               'ui')
    .exportsTo('tracks', function() {

  /**
   * A track that displays the viewport size and scale.
   * @constructor
   * @extends {CanvasBasedTrack}
   */

  var TimelineViewportTrack = base.ui.define(tracks.TimelineCanvasBasedTrack);

  var logOf10 = Math.log(10);
  function log10(x) {
    return Math.log(x) / logOf10;
  }

  TimelineViewportTrack.prototype = {

    __proto__: tracks.TimelineCanvasBasedTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-viewport-track');
      this.strings_secs_ = [];
      this.strings_msecs_ = [];

      this.addEventListener('mousedown', this.onMouseDown);
    },

    onMouseDown: function(e){
      this.placeAndBeginDraggingMarker(e.clientX);
    },


    placeAndBeginDraggingMarker: function(clientX) {
      var viewX = clientX - this.canvasContainer_.offsetLeft;
      var worldX = this.viewport_.xViewToWorld(viewX);
      var marker = this.viewport_.findMarkerNear(worldX, 6);
      var createdMarker = false;
      var movedMarker = false;
      if (!marker) {
        marker = this.viewport_.addMarker(worldX);
        createdMarker = true;
      }
      marker.selected = true;

      var that = this;
      var onMouseMove = function(e) {
        var viewX = e.clientX - that.canvasContainer_.offsetLeft;
        var worldX = that.viewport_.xViewToWorld(viewX);
        marker.positionWorld = worldX;
        movedMarker = true;
      };

      var onMouseUp = function(e) {
        marker.selected = false;
        if(!movedMarker && !createdMarker)
          that.viewport_.removeMarker(marker);
        that.viewport_.dispatchChangeEvent();
        document.removeEventListener('mouseup', onMouseUp);
        document.removeEventListener('mousemove', onMouseMove);
      };

      document.addEventListener('mouseup', onMouseUp);
      document.addEventListener('mousemove', onMouseMove);
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

      for(var i = 0; i < vp.markers.length; ++i) {
        vp.markers[i].drawTriangle(ctx,viewLWorld,viewRWorld,canvasH,vp);
      }

      var idealMajorMarkDistancePix = 150;
      var idealMajorMarkDistanceWorld =
          vp.xViewVectorToWorld(idealMajorMarkDistancePix);

      var majorMarkDistanceWorld;
      var unit;
      var unitDivisor;
      var tickLabels;

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

      var pixelRatio = window.devicePixelRatio || 1;
      ctx.font = (9 * pixelRatio) + 'px sans-serif';

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
        ctx.fillText(tickLabels[roundedUnitValue],
                     curXView + 2 * pixelRatio, 0);
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

  return {
    TimelineViewportTrack: TimelineViewportTrack,
  }
});
