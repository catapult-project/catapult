// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.tracks.ruler_track');

base.require('tracing.constants');
base.require('tracing.tracks.track');
base.require('tracing.tracks.heading_track');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * A track that displays the ruler.
   * @constructor
   * @extends {HeadingTrack}
   */

  var RulerTrack = ui.define('ruler-track', tracing.tracks.HeadingTrack);

  var logOf10 = Math.log(10);
  function log10(x) {
    return Math.log(x) / logOf10;
  }

  RulerTrack.prototype = {
    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('ruler-track');
      this.strings_secs_ = [];
      this.strings_msecs_ = [];
      this.addEventListener('mousedown', this.onMouseDown);

      this.viewportMarkersChange_ = this.viewportMarkersChange_.bind(this);
      viewport.addEventListener('markersChange', this.viewportMarkersChange_);

    },

    detach: function() {
      tracing.tracks.HeadingTrack.prototype.detach.call(this);
      this.viewport.removeEventListener('markersChange',
                                        this.viewportMarkersChange_);
    },

    viewportMarkersChange_: function() {
      if (this.viewport.markers.length < 2)
        this.classList.remove('ruler-track-with-distance-measurements');
      else
        this.classList.add('ruler-track-with-distance-measurements');
    },

    onMouseDown: function(e) {
      if (e.button !== 0)
        return;
      this.placeAndBeginDraggingMarker(e.clientX);
    },

    placeAndBeginDraggingMarker: function(clientX) {
      var pixelRatio = window.devicePixelRatio || 1;

      var viewX =
          (clientX - this.offsetLeft - tracing.constants.HEADING_WIDTH) *
              pixelRatio;
      var worldX = this.viewport.xViewToWorld(viewX);
      var marker = this.viewport.findMarkerNear(worldX, 6);

      var createdMarker = false;
      var movedMarker = false;
      if (!marker) {
        marker = this.viewport.addMarker(worldX);
        createdMarker = true;
      }
      marker.selected = true;

      var onMouseMove = function(e) {
        var viewX =
            (e.clientX - this.offsetLeft - tracing.constants.HEADING_WIDTH) *
                pixelRatio;
        var worldX = this.viewport.xViewToWorld(viewX);

        marker.positionWorld = worldX;
        movedMarker = true;
      }.bind(this);

      var onMouseUp = function(e) {
        marker.selected = false;
        if (!movedMarker && !createdMarker)
          this.viewport.removeMarker(marker);

        document.removeEventListener('mouseup', onMouseUp);
        document.removeEventListener('mousemove', onMouseMove);
      }.bind(this);

      document.addEventListener('mouseup', onMouseUp);
      document.addEventListener('mousemove', onMouseMove);
    },

    drawLine_: function(ctx, x1, y1, x2, y2, color) {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.closePath();
      ctx.strokeStyle = color;
      ctx.stroke();
    },

    drawArrow_: function(ctx, x1, y1, x2, y2, arrowWidth, color) {
      this.drawLine_(ctx, x1, y1, x2, y2, color);

      var dx = x2 - x1;
      var dy = y2 - y1;
      var len = Math.sqrt(dx * dx + dy * dy);
      var perc = (len - 10) / len;
      var bx = x1 + perc * dx;
      var by = y1 + perc * dy;
      var ux = dx / len;
      var uy = dy / len;
      var ax = uy * arrowWidth;
      var ay = -ux * arrowWidth;

      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.moveTo(bx + ax, by + ay);
      ctx.lineTo(x2, y2);
      ctx.lineTo(bx - ax, by - ay);
      ctx.lineTo(bx + ax, by + ay);
      ctx.closePath();
      ctx.fill();
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
      var width = bounds.width * pixelRatio;
      var height = bounds.height * pixelRatio;

      var measurements = this.classList.contains(
          'ruler-track-with-distance-measurements');

      var rulerHeight = measurements ? height / 2 : height;

      var vp = this.viewport;
      vp.drawMarkerArrows(ctx, viewLWorld, viewRWorld, rulerHeight);

      var idealMajorMarkDistancePix = 150 * pixelRatio;
      var idealMajorMarkDistanceWorld =
          vp.xViewVectorToWorld(idealMajorMarkDistancePix);

      var majorMarkDistanceWorld;
      var unit;
      var unitDivisor;
      var tickLabels;

      // The conservative guess is the nearest enclosing 0.1, 1, 10, 100, etc.
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

      var minorTickH = Math.floor(height * 0.25);

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
        ctx.lineTo(curXView, rulerHeight);

        // Minor marks
        for (var i = 1; i < numTicksPerMajor; ++i) {
          var xView = Math.floor(curXView + minorMarkDistancePx * i);
          ctx.moveTo(xView, rulerHeight - minorTickH);
          ctx.lineTo(xView, rulerHeight);
        }

        ctx.stroke();
      }
      // Draw bottom bar.
      ctx.moveTo(0, rulerHeight);
      ctx.lineTo(width, rulerHeight);
      ctx.stroke();

      // Give distance between directly adjacent markers.
      if (measurements) {
        // Obtain a sorted array of markers
        var sortedMarkers = vp.markers.slice();
        sortedMarkers.sort(function(a, b) {
          return a.positionWorld_ - b.positionWorld_;
        });

        // Distance Variables.
        var displayDistance;
        var unitDivisor;
        var displayTextColor = 'rgb(0,0,0)';
        var measurementsPosY = rulerHeight + 2;

        // Arrow Variables.
        var arrowSpacing = 10;
        var arrowColor = 'rgb(128,121,121)';
        var arrowPosY = measurementsPosY + 4;
        var arrowWidthView = 3;
        var spaceForArrowsView = 2 * (arrowWidthView + arrowSpacing);

        for (i = 0; i < sortedMarkers.length - 1; i++) {
          var rightMarker = sortedMarkers[i + 1];
          var leftMarker = sortedMarkers[i];
          var distanceBetweenMarkers =
              rightMarker.positionWorld - leftMarker.positionWorld;
          var distanceBetweenMarkersView =
              vp.xWorldVectorToView(distanceBetweenMarkers);

          var positionInMiddleOfMarkers = leftMarker.positionWorld +
                                              distanceBetweenMarkers / 2;
          var positionInMiddleOfMarkersView =
              vp.xWorldToView(positionInMiddleOfMarkers);

          // Determine units.
          if (distanceBetweenMarkers < 100) {
            unit = 'ms';
            unitDivisor = 1;
          } else {
            unit = 's';
            unitDivisor = 1000;
          }
          // Calculate display value to print.
          displayDistance = distanceBetweenMarkers / unitDivisor;
          var roundedDisplayDistance =
              Math.abs((Math.floor(displayDistance * 1000) / 1000));
          var textToDraw = roundedDisplayDistance + ' ' + unit;
          var textWidthView = ctx.measureText(textToDraw).width;
          var textWidthWorld = vp.xViewVectorToWorld(textWidthView);
          var spaceForArrowsAndTextView = textWidthView +
                                          spaceForArrowsView + arrowSpacing;

          // Set text positions.
          var textLeft = leftMarker.positionWorld +
              (distanceBetweenMarkers / 2) - (textWidthWorld / 2);
          var textRight = textLeft + textWidthWorld;
          var textPosY = measurementsPosY;
          var textLeftView = vp.xWorldToView(textLeft);
          var textRightView = vp.xWorldToView(textRight);
          var leftMarkerView = vp.xWorldToView(leftMarker.positionWorld);
          var rightMarkerView = vp.xWorldToView(rightMarker.positionWorld);
          var textDrawn = false;

          if (spaceForArrowsAndTextView <= distanceBetweenMarkersView) {
            // Print the display distance text.
            ctx.fillStyle = displayTextColor;
            ctx.fillText(textToDraw, textLeftView, textPosY);
            textDrawn = true;
          }

          if (spaceForArrowsView <= distanceBetweenMarkersView) {
            var leftArrowStart;
            var rightArrowStart;
            if (textDrawn) {
              leftArrowStart = textLeftView - arrowSpacing;
              rightArrowStart = textRightView + arrowSpacing;
            } else {
              leftArrowStart = positionInMiddleOfMarkersView;
              rightArrowStart = positionInMiddleOfMarkersView;
            }
            // Draw left arrow.
            this.drawArrow_(ctx, leftArrowStart, arrowPosY,
                leftMarkerView, arrowPosY, arrowWidthView, arrowColor);
            // Draw right arrow.
            this.drawArrow_(ctx, rightArrowStart, arrowPosY,
                rightMarkerView, arrowPosY, arrowWidthView, arrowColor);
          }
        }
        // Draw bottom bar.
        ctx.moveTo(0, rulerHeight * 2);
        ctx.lineTo(width, rulerHeight * 2);
        ctx.stroke();
      }
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
     * @param {Selection} selection Selection to which to add hits.
     */
    addIntersectingItemsInRangeToSelection: function(
        loVX, hiVX, loY, hiY, selection) {
      // Does nothing. There's nothing interesting to pick on the ruler
      // track.
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    }
  };

  return {
    RulerTrack: RulerTrack
  };
});
