// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineAsyncSliceGroup class.
 */
base.defineModule('timeline_async_slice_group')
    .dependsOn('timeline_slice')
    .exportsTo('tracing', function() {

  var TimelineSlice = tracing.TimelineSlice;

  /**
   * A TimelineAsyncSlice represents an interval of time during which an
   * asynchronous operation is in progress. An AsyncSlice consumes no CPU time
   * itself and so is only associated with Threads at its start and end point.
   *
   * @constructor
   */
  function TimelineAsyncSlice(title, colorId, start, args) {
    TimelineSlice.call(this, title, colorId, start, args);
  };

  TimelineAsyncSlice.prototype = {
    __proto__: TimelineSlice.prototype,

    id: undefined,

    startThread: undefined,

    endThread: undefined,

    subSlices: undefined
  };

  /**
   * A group of AsyncSlices, plus code to automatically break them into subRows.
   * @constructor
   */
  function TimelineAsyncSliceGroup(name) {
    this.name = name;
    this.slices = [];
  }

  TimelineAsyncSliceGroup.prototype = {
    __proto__: Object.prototype,

    /**
     * Helper function that pushes the provided slice onto the slices array.
     */
    push: function(slice) {
      this.slices.push(slice);
    },

    /**
     * @return {Number} The number of slices in this group.
     */
    get length() {
      return this.slices.length;
    },

    /**
     * Built automatically by rebuildSubRows().
     */
    subRows_: undefined,

    /**
     * Updates the bounds for this group based on the slices it contains.
     */
    sortSlices_: function() {
      this.slices.sort(function(x, y) {
        return x.start - y.start;
      });
    },

    /**
     * Shifts all the timestamps inside this group forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var sI = 0; sI < this.slices.length; sI++) {
        var slice = this.slices[sI];
        slice.start = (slice.start + amount);
        for (var sJ = 0; sJ < slice.subSlices.length; sJ++)
          slice.subSlices[sJ].start += amount;
      }
    },

    /**
     * Updates the bounds for this group based on the slices it contains.
     */
    updateBounds: function() {
      this.sortSlices_();
      if (this.slices.length) {
        this.minTimestamp = this.slices[0].start;
        this.maxTimestamp = this.slices[this.slices.length - 1].end;
      } else {
        this.minTimestamp = undefined;
        this.maxTimestamp = undefined;
      }
      this.subRows_ = undefined;
    },

    get subRows() {
      if (!this.subRows_)
        this.rebuildSubRows_();
      return this.subRows_;
    },

    /**
     * Breaks up the list of slices into N rows, each of which is a list of
     * slices that are non overlapping.
     *
     * It uses a very simple approach: walk through the slices in sorted order
     * by start time. For each slice, try to fit it in an existing subRow. If it
     * doesn't fit in any subrow, make another subRow.
     */
    rebuildSubRows_: function() {
      this.sortSlices_();
      var subRows = [];
      for (var i = 0; i < this.slices.length; i++) {
        var slice = this.slices[i];

        var found = false;
        for (var j = 0; j < subRows.length; j++) {
          var subRow = subRows[j];
          var lastSliceInSubRow = subRow[subRow.length - 1];
          if (slice.start >= lastSliceInSubRow.end) {
            found = true;
            // Instead of plotting one big slice for the entire
            // TimelineAsyncEvent, we plot each of the subSlices.
            if (slice.subSlices === undefined || slice.subSlices.length < 1)
              throw new Error('TimelineAsyncEvent missing subSlices: ') +
                  slice.name;
            for (var k = 0; k < slice.subSlices.length; k++)
              subRow.push(slice.subSlices[k]);
            break;
          }
        }
        if (!found) {
          var subRow = [];
          if (slice.subSlices !== undefined) {
            for (var k = 0; k < slice.subSlices.length; k++)
              subRow.push(slice.subSlices[k]);
            subRows.push(subRow);
          }
        }
      }
      this.subRows_ = subRows;
    },

    /**
     * Breaks up this group into slices based on start thread.
     *
     * @return {Array} An array of TimelineAsyncSliceGroups where each group has
     * slices that started on the same thread.
     **/
    computeSubGroups: function() {
      var subGroupsByPTID = {};
      for (var i = 0; i < this.slices.length; ++i) {
        var slice = this.slices[i];
        var slicePTID = slice.startThread.ptid;
        if (!subGroupsByPTID[slicePTID])
          subGroupsByPTID[slicePTID] = new TimelineAsyncSliceGroup(this.name);
        subGroupsByPTID[slicePTID].slices.push(slice);
      }
      var groups = [];
      for (var ptid in subGroupsByPTID) {
        var group = subGroupsByPTID[ptid];
        group.updateBounds();
        groups.push(group);
      }
      return groups;
    }
  };

  return {
    TimelineAsyncSlice: TimelineAsyncSlice,
    TimelineAsyncSliceGroup: TimelineAsyncSliceGroup
  }
});