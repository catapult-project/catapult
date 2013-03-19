// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the SliceGroup class.
 */
base.require('range');
base.require('slice');
base.require('color_scheme');
base.require('filter');

base.exportTo('tracing', function() {
  var Slice = tracing.Slice;

  /**
   * A group of Slices, plus code to create them from B/E events, as
   * well as arrange them into subRows.
   *
   * Do not mutate the slices array directly. Modify it only by
   * SliceGroup mutation methods.
   *
   * @constructor
   * @param {function(new:Slice, category, title, colorId, start, args)}
   *     opt_sliceConstructor The constructor to use when creating slices.
   */
  function SliceGroup(opt_sliceConstructor) {
    var sliceConstructor = opt_sliceConstructor || Slice;
    this.sliceConstructor = sliceConstructor;

    this.openPartialSlices_ = [];

    this.slices = [];
    this.bounds = new base.Range();
  }

  SliceGroup.prototype = {
    __proto__: Object.prototype,

    /**
     * Helper function that pushes the provided slice onto the slices array.
     * @param {Slice} slice The slice to be added to the slices array.
     */
    pushSlice: function(slice) {
      this.slices.push(slice);
      return slice;
    },

    /**
     * Helper function that pushes the provided slice onto the slices array.
     * @param {Array.<Slice>} slices An array of slices to be added.
     */
    pushSlices: function(slices) {
      this.slices.push.apply(this.slices, slices);
    },

    /**
     * Opens a new slice in the group's slices.
     *
     * Calls to beginSlice and
     * endSlice must be made with non-monotonically-decreasing timestamps.
     *
     * @param {String} title Title of the slice to add.
     * @param {Number} ts The timetsamp of the slice, in milliseconds.
     * @param {Object.<string, Object>} opt_args Arguments associated with
     * the slice.
     */
    beginSlice: function(category, title, ts, opt_args) {
      if (this.openPartialSlices_.length) {
        var prevSlice = this.openPartialSlices_[
            this.openPartialSlices_.length - 1];
        if (ts < prevSlice.start)
          throw new Error('Slices must be added in increasing timestamp order');
      }

      var colorId = tracing.getStringColorId(title);
      var slice = new this.sliceConstructor(category, title, colorId, ts,
                                            opt_args ? opt_args : {});
      this.openPartialSlices_.push(slice);
      return slice;
    },

    isTimestampValidForBeginOrEnd: function(ts) {
      if (!this.openPartialSlices_.length)
        return true;
      var top = this.openPartialSlices_[this.openPartialSlices_.length - 1];
      return ts >= top.start;
    },

    /**
     * @return {Number} The number of beginSlices for which an endSlice has not
     * been issued.
     */
    get openSliceCount() {
      return this.openPartialSlices_.length;
    },

    /**
     * Ends the last begun slice in this group and pushes it onto the slice
     * array.
     *
     * @param {Number} ts Timestamp when the slice ended.
     * @return {Slice} slice.
     */
    endSlice: function(ts) {
      if (!this.openSliceCount)
        throw new Error('endSlice called without an open slice');
      var slice = this.openPartialSlices_[this.openSliceCount - 1];
      this.openPartialSlices_.splice(this.openSliceCount - 1, 1);
      if (ts < slice.start)
        throw new Error('Slice ' + slice.name +
                        ' end time is before its start.');

      slice.duration = ts - slice.start;
      this.pushSlice(slice);

      return slice;
    },

    /**
     * Closes any open slices.
     * @param {Number} opt_maxTimestamp The end time to use for the closed
     * slices. If not provided,
     * the max timestamp for this slice is provided.
     */
    autoCloseOpenSlices: function(opt_maxTimestamp) {
      if (!opt_maxTimestamp) {
        this.updateBounds();
        opt_maxTimestamp = this.bounds.max;
      }
      while (this.openSliceCount > 0) {
        var slice = this.endSlice(opt_maxTimestamp);
        slice.didNotFinish = true;
      }
    },

    /**
     * Shifts all the timestamps inside this group forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var sI = 0; sI < this.slices.length; sI++) {
        var slice = this.slices[sI];
        slice.start = (slice.start + amount);
      }
      for (var sI = 0; sI < this.openPartialSlices_.length; sI++) {
        var slice = this.openPartialSlices_[i];
        slice.start = (slice.start + amount);
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

      if (this.openPartialSlices_.length) {
        this.bounds.addValue(this.openPartialSlices_[0].start);
        this.bounds.addValue(
            this.openPartialSlices_[this.openPartialSlices_.length - 1].start);
      }
    }
  };

  return {
    SliceGroup: SliceGroup
  };
});
