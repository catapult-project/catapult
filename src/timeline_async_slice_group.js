// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineAsyncSliceGroup class.
 */
base.require('timeline_slice');
base.exportTo('tracing', function() {

  var TimelineSlice = tracing.TimelineSlice;

  /**
   * A TimelineAsyncSlice represents an interval of time during which an
   * asynchronous operation is in progress. An AsyncSlice consumes no CPU time
   * itself and so is only associated with Threads at its start and end point.
   *
   * @constructor
   */
  function TimelineAsyncSlice(category, title, colorId, start, args) {
    TimelineSlice.call(this, category, title, colorId, start, args);
  };

  TimelineAsyncSlice.prototype = {
    __proto__: TimelineSlice.prototype,

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'startThread' || key == 'endThread') {
          obj[key] = this[key].ptid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    id: undefined,

    startThread: undefined,

    endThread: undefined,

    subSlices: undefined
  };

  /**
   * A group of AsyncSlices.
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
      if (this.slices.length) {
        var minTimestamp = Number.MAX_VALUE;
        var maxTimestamp = -Number.MAX_VALUE;
        for (var i = 0; i < this.slices.length; i++) {
          if (this.slices[i].start < minTimestamp)
            minTimestamp = this.slices[i].start;
          if (this.slices[i].end > maxTimestamp)
            maxTimestamp = this.slices[i].end;
        }
        this.minTimestamp = minTimestamp;
        this.maxTimestamp = maxTimestamp;
      } else {
        this.minTimestamp = undefined;
        this.maxTimestamp = undefined;
      }
    },

    /**
     * Breaks up this group into slices based on start thread.
     *
     * @return {Array} An array of TimelineAsyncSliceGroups where each group has
     * slices that started on the same thread.
     */
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
  };
});
