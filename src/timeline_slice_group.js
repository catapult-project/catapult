// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineSliceGroup class.
 */
base.defineModule('timeline_slice_group')
    .dependsOn('timeline_slice', 'timeline_color_scheme')
    .exportsTo('tracing', function() {
  var TimelineSlice = tracing.TimelineSlice;

  /**
   * A group of TimelineSlices, plus code to create them from B/E events, as
   * well as arrange them into subRows.
   *
   * Do not mutate the slices array directly. Modify it only by
   * TimelineSliceGroup mutation methods.
   *
   * @constructor
   * @param {function(new:TimelineSlice, title, colorId, start, args)}
   *     opt_sliceConstructor The constructor to use when creating slices.
   */
  function TimelineSliceGroup(opt_sliceConstructor) {
    var sliceConstructor = opt_sliceConstructor || TimelineSlice;
    this.sliceConstructor = sliceConstructor;

    this.openPartialSlices_ = [];

    this.slices = [];
    this.subRows_ = undefined;
    this.badSlices_ = undefined;
  }

  TimelineSliceGroup.prototype = {
    __proto__: Object.prototype,

    /**
     * Helper function that pushes the provided slice onto the slices array.
     * @param {TimelineSlice} slice The slice to be added to the slices array.
     */
    pushSlice: function(slice) {
      this.slices.push(slice);
      this.subRows_ = undefined;
      return slice;
    },

    /**
     * Helper function that pushes the provided slice onto the slices array.
     * @param {Array.<TimelineSlice>} slices An array of slices to be added.
     */
    pushSlices: function(slices) {
      this.slices.push.apply(this.slices, slices);
      this.subRows_ = undefined;
    },

    /**
     * Opens a new slice in the group's slices.
     *
     * Calls to beginSlice and
     * endSlice must be made with non-monotonically-decreasing timestamps.
     *
     * @param {String} title Title of the slice to add.
     * @param {Number] ts The timetsamp of the slice, in milliseconds.
     * @param {Object.<string, Object>} opt_args Arguments associated with
     * the slice.
     */
    beginSlice: function(title, ts, opt_args) {
      if (this.openPartialSlices_.length) {
        var prevSlice = this.openPartialSlices_[
            this.openPartialSlices_.length - 1];
        if (ts < prevSlice.start)
          throw new Error("Slices must be added in increasing timestamp order");
      }

      var colorId = tracing.getStringColorId(title);
      var slice = new this.sliceConstructor(title, colorId, ts,
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
     * @return {TimelineSlice} slice.
     */
    endSlice: function(ts) {
      if (!this.openSliceCount)
        throw new Error('endSlice called without an open slice');
      var slice = this.openPartialSlices_[this.openSliceCount - 1];
      this.openPartialSlices_.splice(this.openSliceCount - 1, 1);
      if (ts < slice.start)
        throw new Error("Slice " + slice.name +
                        " end time is before its start.");

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
        opt_maxTimestamp = this.maxTimestamp;
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
      var vals = [];
      if (this.slices.length) {
        var minTimestamp = Number.MAX_VALUE;
        var maxTimestamp = -Number.MAX_VALUE;
        for (var i = 0; i < this.slices.length; i++) {
          if (this.slices[i].start < minTimestamp)
            minTimestamp = this.slices[i].start;
          if (this.slices[i].end > maxTimestamp)
            maxTimestamp = this.slices[i].end;
        }
        vals.push(minTimestamp);
        vals.push(maxTimestamp);
      }

      if (this.openPartialSlices_.length) {
        vals.push(this.openPartialSlices_[0].start);
        vals.push(
            this.openPartialSlices_[this.openPartialSlices_.length - 1].start);
      }

      if (vals.length) {
        this.minTimestamp = Math.min.apply(Math, vals);
        this.maxTimestamp = Math.max.apply(Math, vals);
      } else {
        this.minTimestamp = undefined;
        this.maxTimestamp = undefined;
      }
      this.subRows_ = undefined;
    },

    /**
     * @return {Array.<Array.<TimelineSlice>>} An array of array of slices,
     * organized into rows based on their nesting structure. Each item in the
     * array represents a single logical track that can be handed to a
     * TimelineSliceTrack.
     *
     * DO NOT modify the returned array, it is automatically built for you.
     * Also, while trying to push to the returned array throw an error, not all
     * types of mutation will fail (for performance reasons).
     */
    get subRows() {
      if (!this.subRows_)
        this.rebuildSubRows_();
      return this.subRows_;
    },

    /**
     * @return {Array.<TimelineSlice>} An array of slices that could not be put
     * into the subRows data structure due to nesting violations. If all slices
     * are placed successfully, then badSlices.length is 0.
     */
    get badSlices() {
      if (!this.subRows_)
        this.rebuildSubRows_();
      return this.badSlices_;
    },

    /**
     * Breaks up the list of slices into N rows, each of which is a list of
     * slices that are non overlapping.
     */
    rebuildSubRows_: function() {
      // This function works by walking through slices by start time.
      //
      // The basic idea here is to insert each slice as deep into the subrow
      // list as it can go such that every subSlice is fully contained by its
      // parent slice.
      //
      // Visually, if we start with this:
      //  0:  [    a       ]
      //  1:    [  b  ]
      //  2:    [c][d]
      //
      // To place this slice:
      //               [e]
      // We first check row 2's last item, [d]. [e] wont fit into [d] (they dont
      // even intersect). So we go to row 1. That gives us [b], and [d] wont fit
      // into that either. So, we go to row 0 and its last slice, [a]. That can
      // completely contain [e], so that means we should add [e] as a subchild
      // of [a]. That puts it on row 1, yielding:
      //  0:  [    a       ]
      //  1:    [  b  ][e]
      //  2:    [c][d]
      //
      // If we then get this slice:
      //                      [f]
      // We do the same deepest-to-shallowest walk of the subrows trying to fit
      // it. This time, it doesn't fit in any open slice. So, we simply append
      // it to row 0:
      //  0:  [    a       ]  [f]
      //  1:    [  b  ][e]
      //  2:    [c][d]
      var slices = this.slices;
      var ops = [];
      for (var i = 0; i < slices.length; i++) {
        if (slices[i].subSlices)
          slices[i].subSlices.splice(0,
                                     slices[i].subSlices.length);
        ops.push(i);
      }

      ops.sort(function(ix,iy) {
        var x = slices[ix];
        var y = slices[iy];
        if (x.start != y.start)
          return x.start - y.start;
        return ix - iy;
      });

      var subRows = [[]];
      var badSlices = [];

      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        var slice = slices[op];

        // Try to fit the slice into the existing subrows.
        var inserted = false;
        for (var j = subRows.length - 1; j >= 0; j--) {
          if (subRows[j].length == 0)
            continue;

          var insertedSlice = subRows[j][subRows[j].length - 1];
          if (slice.start < insertedSlice.start) {
            badSlices.push(slice);
            inserted = true;
          }
          if (slice.start >= insertedSlice.start &&
              slice.end   <= insertedSlice.end) {
            // Insert it into subRow j + 1.
            while (subRows.length <= j + 1)
              subRows.push([]);
            subRows[j + 1].push(slice);
            if (insertedSlice.subSlices)
              insertedSlice.subSlices.push(slice);
            inserted = true;
            break;
          }
        }
        if (inserted)
          continue;

        // Append it to subRow[0] as a root.
        subRows[0].push(slice);
      }

      this.badSlices_ = badSlices;
      this.subRows_ = subRows;

      // Prevent accidental messing around with these arrays.
      this.subRows_.__defineGetter__('push', function() {
        throw Error("Do not modify elements in this array, ever!");
      });
      for (var i = 0; i < this.subRows_.length; i++) {
        this.subRows_[i].__defineGetter__('push', function() {
          throw Error("Do not modify elements in this array!");
        });
      }
    },
  };

  return {
    TimelineSliceGroup: TimelineSliceGroup
  }
});