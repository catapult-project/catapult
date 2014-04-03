// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the AsyncSliceGroup class.
 */
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.async_slice');

tvcm.exportTo('tracing.trace_model', function() {
  /**
   * A group of AsyncSlices.
   * @constructor
   */
  function AsyncSliceGroup() {
    this.slices = [];
    this.bounds = new tvcm.Range();
  }

  AsyncSliceGroup.prototype = {
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
      this.bounds.reset();
      for (var i = 0; i < this.slices.length; i++) {
        this.bounds.addValue(this.slices[i].start);
        this.bounds.addValue(this.slices[i].end);
      }
    },

    /**
     * Breaks up this group into slices based on start thread.
     *
     * @return {Array} An array of AsyncSliceGroups where each group has
     * slices that started on the same thread.
     */
    computeSubGroups: function() {
      var subGroupsByGUID = {};
      for (var i = 0; i < this.slices.length; ++i) {
        var slice = this.slices[i];
        var sliceGUID = slice.startThread.guid;
        if (!subGroupsByGUID[sliceGUID])
          subGroupsByGUID[sliceGUID] = new AsyncSliceGroup();
        subGroupsByGUID[sliceGUID].slices.push(slice);
      }
      var groups = [];
      for (var guid in subGroupsByGUID) {
        var group = subGroupsByGUID[guid];
        group.updateBounds();
        groups.push(group);
      }
      return groups;
    },

    iterateAllEvents: function(callback, opt_this) {
      for (var i = 0; i < this.slices.length; i++) {
        var slice = this.slices[i];
        callback.call(opt_this, slice);
        if (slice.subSlices)
          slice.subSlices.forEach(callback, opt_this);
      }
    }
  };

  return {
    AsyncSliceGroup: AsyncSliceGroup
  };
});
