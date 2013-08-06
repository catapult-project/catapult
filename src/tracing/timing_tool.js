// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.constants');

/**
 * @fileoverview Provides the TimingTool class.
 */
base.exportTo('tracing', function() {

  var constants = tracing.constants;

  /**
   * Tool for taking time measurements in the TimelineTrackView using
   * Viewportmarkers.
   * @constructor
   */
  var TimingTool = function(viewport, markerView) {
    this.viewport = viewport;
    this.markerView_ = markerView;

    this.rangeStartMarker_ = viewport.createMarker(0);
    this.rangeEndMarker_ = viewport.createMarker(0);
    this.cursorMarker_ = viewport.createMarker(0);
    this.activeMarker_ = this.cursorMarker_;
  };

  TimingTool.prototype = {

    getWorldXFromEvent_: function(e) {
      var pixelRatio = window.devicePixelRatio || 1;
      var viewX =
          (e.clientX - this.markerView_.offsetLeft - constants.HEADING_WIDTH) *
              pixelRatio;
      return this.viewport.xViewToWorld(viewX);
    },

    onEnterTiming: function(e) {
      // Show the cursor marker if it was the active marker, otherwise the two
      // range markers should be left.
      if (this.activeMarker_ === this.cursorMarker_)
        this.viewport.addMarker(this.cursorMarker_);
    },

    onBeginTiming: function(e) {
      var mouseEvent = e.data;
      var worldX = this.getWorldXFromEvent_(mouseEvent);

      // Check if click was on a range marker that can be moved.
      if (!this.activeMarker_) {
        var marker = this.viewport.findMarkerNear(worldX, 6);
        if (marker === this.rangeStartMarker_ ||
            marker === this.rangeEndMarker_) {
          // Set the clicked marker as active marker so it will be moved.
          this.activeMarker_ = marker;
          marker.selected = true;
          return;
        }
      } else {
        // Otherwise start selecting a new range by hiding the cursor marker and
        // adding the end marker. This is skipped if there was already a range
        // on screen.
        this.viewport.removeMarker(this.cursorMarker_);
        this.viewport.addMarker(this.rangeEndMarker_);
      }

      // Set both range markers to the mouse position and select them.
      this.rangeStartMarker_.positionWorld = worldX;
      this.rangeEndMarker_.positionWorld = worldX;

      this.rangeStartMarker_.selected = true;
      this.rangeEndMarker_.selected = true;

      // The end marker is the one that is moved.
      this.activeMarker_ = this.rangeEndMarker_;
    },

    onUpdateTiming: function(e) {
      var mouseEvent = e.data;
      var worldX = this.getWorldXFromEvent_(mouseEvent);

      // Update the position of the active marker to the cursor position.
      // This is either the cursor marker, the end marker when creating a range,
      // or one of the range markers when they are moved.
      if (this.activeMarker_) {
        this.activeMarker_.positionWorld = worldX;

        // When creating a range, only show the start marker after the range
        // exceeds a certain amount. This prevents a short flicker showing the
        // dimmed areas left and right of the range when clicking.
        if (this.rangeStartMarker_.selected && this.rangeEndMarker_.selected) {
          var rangeX = Math.abs(this.rangeStartMarker_.positionView -
                                this.rangeEndMarker_.positionView);
          if (rangeX >= constants.MIN_MOUSE_SELECTION_DISTANCE)
            this.viewport.addMarker(this.rangeStartMarker_);
        }
        return;
      }

      // If there is no active marker then look for a marker close to the cursor
      // and indicate that it can be moved by displaying it selected.
      var marker = this.viewport.findMarkerNear(worldX, 6);
      if (marker === this.rangeStartMarker_ ||
          marker === this.rangeEndMarker_) {
        marker.selected = true;
      } else {
        // Otherwise deselect markers that may have been selected before.
        this.rangeEndMarker_.selected = false;
        this.rangeStartMarker_.selected = false;
      }
    },

    onEndTiming: function(e) {
      var mouseEvent = e.data;

      if (!this.activeMarker_ || !this.activeMarker_.selected)
        return;

      e.consumed = true;

      // Check if a range selection is finished now.
      if (this.rangeStartMarker_.selected && this.rangeEndMarker_.selected) {
        var rangeX = Math.abs(this.rangeStartMarker_.positionView -
                              this.rangeEndMarker_.positionView);

        // The range is only valid when it exceeds the minimum mouse selection
        // distance, otherwise it could have been just a click.
        if (rangeX >= constants.MIN_MOUSE_SELECTION_DISTANCE) {
          this.rangeStartMarker_.selected = false;
          this.rangeEndMarker_.selected = false;
          this.activeMarker_ = null;
        } else {
          // If the range is not valid, hide it and activate the cursor marker.
          this.viewport.removeMarker(this.rangeStartMarker_);
          this.viewport.removeMarker(this.rangeEndMarker_);

          this.viewport.addMarker(this.cursorMarker_);
          this.cursorMarker_.positionWorld =
              this.getWorldXFromEvent_(mouseEvent);
          this.activeMarker_ = this.cursorMarker_;
          e.consumed = false;
        }
        return;
      }

      // Deselect and deactivate a range marker that was moved.
      this.activeMarker_.selected = false;
      this.activeMarker_ = null;
    },

    onExitTiming: function(e) {
      // If there is a selected range the markers are left on screen, but the
      // cursor marker gets removed.
      if (this.activeMarker_ === this.cursorMarker_)
        this.viewport.removeMarker(this.cursorMarker_);
    }
  };

  return {
    TimingTool: TimingTool
  };
});
