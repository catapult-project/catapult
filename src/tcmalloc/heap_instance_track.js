// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tcmalloc.heap_instance_track');

base.require('base.sorted_array_utils');
base.require('tracing.tracks.heading_track');
base.require('tracing.tracks.object_instance_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('tcmalloc', function() {

  var EventPresenter = tracing.EventPresenter;

  /**
   * A track that displays heap memory data.
   * @constructor
   * @extends {HeadingTrack}
   */

  var HeapInstanceTrack = ui.define(
      'heap-instance-track', tracing.tracks.HeadingTrack);

  HeapInstanceTrack.prototype = {

    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('heap-instance-track');
      this.objectInstance_ = null;
    },

    set objectInstances(objectInstances) {
      if (!objectInstances) {
        this.objectInstance_ = [];
        return;
      }
      if (objectInstances.length != 1)
        throw new Error('Bad object instance count.');
      this.objectInstance_ = objectInstances[0];
      this.maxBytes_ = this.computeMaxBytes_(
          this.objectInstance_.snapshots);
    },

    computeMaxBytes_: function(snapshots) {
      var maxBytes = 0;
      for (var i = 0; i < snapshots.length; i++) {
        var snapshot = snapshots[i];
        // Sum all the current allocations in this snapshot.
        var traceNames = Object.keys(snapshot.heap_.children);
        var sumBytes = 0;
        for (var j = 0; j < traceNames.length; j++) {
          sumBytes += snapshot.heap_.children[traceNames[j]].currentBytes;
        }
        // Keep track of the maximum across all snapshots.
        if (sumBytes > maxBytes)
          maxBytes = sumBytes;
      }
      return maxBytes;
    },

    get height() {
      return window.getComputedStyle(this).height;
    },

    set height(height) {
      this.style.height = height;
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

      // Culling parameters.
      var dt = this.viewport.currentDisplayTransform;

      // Scale by the size of the largest snapshot.
      var maxBytes = this.maxBytes_;

      var objectSnapshots = this.objectInstance_.snapshots;
      var lowIndex = base.findLowIndexInSortedArray(
          objectSnapshots,
          function(snapshot) {
            return snapshot.ts;
          },
          viewLWorld);
      // Assure that the stack with the left edge off screen still gets drawn
      if (lowIndex > 0)
        lowIndex -= 1;

      for (var i = lowIndex; i < objectSnapshots.length; ++i) {
        var snapshot = objectSnapshots[i];

        var left = snapshot.ts;
        if (left > viewRWorld)
          break;
        var leftView = dt.xWorldToView(left);
        if (leftView < 0)
          leftView = 0;

        // Compute the edges for the column graph bar.
        var right;
        if (i != objectSnapshots.length - 1) {
          right = objectSnapshots[i + 1].ts;
        } else {
          // If this is the last snaphot of multiple snapshots, use the width of
          // the previous snapshot for the width.
          if (objectSnapshots.length > 1)
            right = objectSnapshots[i].ts + (objectSnapshots[i].ts -
                    objectSnapshots[i - 1].ts);
          else
            // If there's only one snapshot, use max bounds as the width.
            right = this.objectInstance_.parent.model.bounds.max;
        }

        var rightView = dt.xWorldToView(right);
        if (rightView > width)
          rightView = width;

        // Floor the bounds to avoid a small gap between stacks.
        leftView = Math.floor(leftView);
        rightView = Math.floor(rightView);

        // Draw a stacked bar graph. Largest item is stored first in the
        // heap data structure, so iterate backwards. Likewise draw from
        // the bottom of the bar upwards.
        var currentY = height;
        var keys = Object.keys(snapshot.heap_.children);
        for (var k = keys.length - 1; k >= 0; k--) {
          var trace = snapshot.heap_.children[keys[k]];
          if (this.objectInstance_.selectedTraces &&
              this.objectInstance_.selectedTraces.length > 0 &&
              this.objectInstance_.selectedTraces[0] == keys[k]) {
            // A trace selected in the analysis view is bright yellow.
            ctx.fillStyle = 'rgb(239, 248, 206)';
          } else
            ctx.fillStyle = EventPresenter.getHeapSnapshotColor(snapshot, k);

          var barHeight = height * trace.currentBytes / maxBytes;
          ctx.fillRect(leftView, currentY - barHeight,
                       Math.max(rightView - leftView, 1), barHeight);
          currentY -= barHeight;
        }
      }
      ctx.lineWidth = 1;
    },

    addEventsToTrackMap: function(eventToTrackMap) {
      var objectSnapshots = this.objectInstance_.snapshots;
      objectSnapshots.forEach(function(obj) {
        eventToTrackMap.addEvent(obj, this);
      }, this);
    },

    /**
     * Used to hit-test clicks in the graph.
     */
    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      function onSnapshot(snapshot) {
        selection.push(snapshot);
      }

      var snapshots = this.objectInstance_.snapshots;
      var maxBounds = this.objectInstance_.parent.model.bounds.max;

      base.iterateOverIntersectingIntervals(
          snapshots,
          function(x) { return x.ts; },
          function(x, i) {
            if (i == snapshots.length - 1) {
              if (snapshots.length == 1)
                return maxBounds;

              return snapshots[i].ts - snapshots[i - 1].ts;
            }

            return snapshots[i + 1].ts - snapshots[i].ts;
          },
          loWX, hiWX,
          onSnapshot);
    },

    /**
     * Add the item to the left or right of the provided item, if any, to the
     * selection.
     * @param {slice} The current slice.
     * @param {Number} offset Number of slices away from the object to look.
     * @param {Selection} selection The selection to add an event to,
     * if found.
     * @return {boolean} Whether an event was found.
     * @private
     */
    addItemNearToProvidedEventToSelection: function(event, offset, selection) {
      if (!(event instanceof tracing.trace_model.ObjectSnapshot))
        throw new Error('Unrecognized event');
      var objectSnapshots = this.objectInstance_.snapshots;
      var index = objectSnapshots.indexOf(event);
      var newIndex = index + offset;
      if (newIndex >= 0 && newIndex < objectSnapshots.length) {
        selection.push(objectSnapshots[newIndex]);
        return true;
      }
      return false;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    },

    addClosestEventToSelection: function(worldX, worldMaxDist, loY, hiY,
                                         selection) {
      var snapshot = base.findClosestElementInSortedArray(
          this.objectInstance_.snapshots,
          function(x) { return x.ts; },
          worldX,
          worldMaxDist);

      if (!snapshot)
        return;

      selection.push(snapshot);
    }
  };

  tracing.tracks.ObjectInstanceTrack.register(
      'memory::Heap', HeapInstanceTrack);

  return {
    HeapInstanceTrack: HeapInstanceTrack
  };
});
