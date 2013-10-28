// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.range');
base.require('tracing.constants');
base.require('tracing.selection');
base.require('tracing.trace_model.slice');

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
  var TimingTool = function(viewport, targetElement) {
    this.viewport = viewport;

    this.rangeStartMarker_ = viewport.createMarker(0);
    this.rangeEndMarker_ = viewport.createMarker(0);
    this.cursorMarker_ = viewport.createMarker(0);
    this.activeMarker_ = this.cursorMarker_;

    // Prepare the event handlers to be added and removed repeatedly.
    this.onMouseMove_ = this.onMouseMove_.bind(this);
    this.onDblClick_ = this.onDblClick_.bind(this);
    this.targetElement_ = targetElement;
  };

  TimingTool.prototype = {

    getWorldXFromEvent_: function(e) {
      var pixelRatio = window.devicePixelRatio || 1;
      var modelTrackContainer = this.viewport.modelTrackContainer;
      var viewX = (e.clientX -
                   modelTrackContainer.offsetLeft -
                   constants.HEADING_WIDTH) * pixelRatio;
      return this.viewport.currentDisplayTransform.xViewToWorld(viewX);
    },

    onEnterTiming: function(e) {
      // Show the cursor marker if it was the active marker, otherwise the two
      // range markers should be left.
      if (this.activeMarker_ === this.cursorMarker_)
        this.viewport.addMarker(this.cursorMarker_);

      this.targetElement_.addEventListener('mousemove', this.onMouseMove_);
      this.targetElement_.addEventListener('dblclick', this.onDblClick_);
    },

    onBeginTiming: function(e) {
      var worldX = this.getWorldXFromEvent_(e);

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

      // Set the range markers to the mouse or snapped position and select them.
      var snapPos = this.getSnappedToEventPosition_(e);
      this.updateMarkerToSnapPosition_(this.rangeStartMarker_, snapPos);
      this.updateMarkerToSnapPosition_(this.rangeEndMarker_, snapPos);

      this.rangeStartMarker_.selected = true;
      this.rangeEndMarker_.selected = true;

      // The end marker is the one that is moved.
      this.activeMarker_ = this.rangeEndMarker_;
    },

    onUpdateTiming: function(e) {
      if (!this.activeMarker_ || this.activeMarker_ === this.cursorMarker_)
        return;

      // Update the position of the active marker to the cursor position.
      // This is either the end marker when creating a range, or one of the
      // range markers when they are moved.
      var snapPos = this.getSnappedToEventPosition_(e);
      this.updateMarkerToSnapPosition_(this.activeMarker_, snapPos);

      // When creating a range, only show the start marker after the range
      // exceeds a certain amount. This prevents a short flicker showing the
      // dimmed areas left and right of the range when clicking.
      if (this.rangeStartMarker_.selected && this.rangeEndMarker_.selected) {
        var rangeX = Math.abs(this.rangeStartMarker_.positionView -
                              this.rangeEndMarker_.positionView);
        if (rangeX >= constants.MIN_MOUSE_SELECTION_DISTANCE)
          this.viewport.addMarker(this.rangeStartMarker_);
      }
    },

    onEndTiming: function(e) {
      if (!this.activeMarker_ || !this.activeMarker_.selected)
        return;

      e.preventDefault();

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
              this.getWorldXFromEvent_(e);
          this.activeMarker_ = this.cursorMarker_;
          e.preventDefault();
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

      this.targetElement_.removeEventListener('mousemove', this.onMouseMove_);
      this.targetElement_.removeEventListener('dblclick', this.onDblClick_);
    },

    onMouseMove_: function(e) {
      var worldX = this.getWorldXFromEvent_(e);

      if (this.activeMarker_) {
        // Update the position of the cursor marker.
        if (this.activeMarker_ === this.cursorMarker_) {
          var snapPos = this.getSnappedToEventPosition_(e);
          this.updateMarkerToSnapPosition_(this.cursorMarker_, snapPos);
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

    onDblClick_: function(e) {
      var modelTrackContainer = this.viewport.modelTrackContainer;
      var modelTrackContainerRect = modelTrackContainer.getBoundingClientRect();

      var eventWorldX = this.getWorldXFromEvent_(e);
      var y = e.clientY;

      var selection = new tracing.Selection();
      modelTrackContainer.addClosestEventToSelection(
          eventWorldX, Infinity, y, y, selection);

      if (!selection.length)
        return;

      var slice = selection[0];

      if (!(slice instanceof tracing.trace_model.Slice))
        return;

      if (slice.start > eventWorldX || slice.end < eventWorldX)
        return;

      var track = this.viewport.trackForEvent(slice);
      var trackRect = track.getBoundingClientRect();

      var snapPos = {
        x: slice.start,
        y: trackRect.top +
            modelTrackContainer.scrollTop - modelTrackContainerRect.top,
        height: trackRect.height,
        snapped: true
      };
      this.updateMarkerToSnapPosition_(this.rangeStartMarker_, snapPos);
      snapPos.x = slice.end;
      this.updateMarkerToSnapPosition_(this.rangeEndMarker_, snapPos);

      this.viewport.addMarker(this.rangeStartMarker_);
      this.viewport.addMarker(this.rangeEndMarker_);
      this.viewport.removeMarker(this.cursorMarker_);
      this.activeMarker_ = null;
    },

    /**
     * Get the closest position of an event within a vertical range of the mouse
     * position if possible, otherwise use the position of the mouse pointer.
     * @param {MouseEvent} e Mouse event with the current mouse coordinates.
     * @return {
     *   {Number} x, The x coordinate in world space.
     *   {Number} y, The y coordinate in world space.
     *   {Number} height, The height of the event.
     *   {boolean} snapped Whether the coordinates are from a snapped event or
     *     the mouse position.
     * }
     */
    getSnappedToEventPosition_: function(e) {
      var pixelRatio = window.devicePixelRatio || 1;
      var EVENT_SNAP_RANGE = 16 * pixelRatio;

      var modelTrackContainer = this.viewport.modelTrackContainer;
      var modelTrackContainerRect = modelTrackContainer.getBoundingClientRect();

      var viewport = this.viewport;
      var dt = viewport.currentDisplayTransform;
      var worldMaxDist = dt.xViewVectorToWorld(EVENT_SNAP_RANGE);

      var worldX = this.getWorldXFromEvent_(e);
      var mouseY = e.clientY;

      var selection = new tracing.Selection();

      // Look at the track under mouse position first for better performance.
      modelTrackContainer.addClosestEventToSelection(
          worldX, worldMaxDist, mouseY, mouseY, selection);

      // Look at all tracks visible on screen.
      if (!selection.length) {
        modelTrackContainer.addClosestEventToSelection(
            worldX, worldMaxDist,
            modelTrackContainerRect.top, modelTrackContainerRect.bottom,
            selection);
      }

      var minDistX = worldMaxDist;
      var minDistY = Infinity;
      var pixWidth = dt.xViewVectorToWorld(1);

      // Create result object with the mouse coordinates.
      var result = {
        x: worldX,
        y: mouseY - modelTrackContainerRect.top,
        height: 0,
        snapped: false
      };

      var eventBounds = new base.Range();
      for (var i = 0; i < selection.length; i++) {
        var event = selection[i];
        var track = viewport.trackForEvent(event);
        var trackRect = track.getBoundingClientRect();

        eventBounds.reset();
        event.addBoundsToRange(eventBounds);
        var eventX;
        if (Math.abs(eventBounds.min - worldX) <
            Math.abs(eventBounds.max - worldX)) {
          eventX = eventBounds.min;
        } else {
          eventX = eventBounds.max;
        }

        var distX = eventX - worldX;

        var eventY = trackRect.top;
        var eventHeight = trackRect.height;
        var distY = Math.abs(eventY + eventHeight / 2 - mouseY);

        // Prefer events with a closer y position if their x difference is below
        // the width of a pixel.
        if ((distX <= minDistX || Math.abs(distX - minDistX) < pixWidth) &&
            distY < minDistY) {
          minDistX = distX;
          minDistY = distY;

          // Retrieve the event position from the hit.
          result.x = eventX;
          result.y = eventY +
              modelTrackContainer.scrollTop - modelTrackContainerRect.top;
          result.height = eventHeight;
          result.snapped = true;
        }
      }

      return result;
    },

    /**
     * Update the marker to the snapped position.
     * @param {ViewportMarker} marker The marker to be updated.
     * @param {
     *   {Number} x, The new positionWorld of the marker.
     *   {Number} y, The new indicatorY of the marker.
     *   {Number} height, The new indicatorHeight of the marker.
     *   {boolean} snapped Whether the coordinates are from a snapped event or
     *     the mouse position.
     * } snapPos
     */
    updateMarkerToSnapPosition_: function(marker, snapPos) {
      marker.setSnapIndicator(snapPos.snapped, snapPos.y, snapPos.height);
      marker.positionWorld = snapPos.x;
    }
  };

  return {
    TimingTool: TimingTool
  };
});
