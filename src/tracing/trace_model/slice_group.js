// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the SliceGroup class.
 */
base.require('base.range');
base.require('tracing.trace_model.slice');
base.require('tracing.color_scheme');
base.require('tracing.filter');

base.exportTo('tracing.trace_model', function() {
  var Slice = tracing.trace_model.Slice;

  /**
   * A group of Slices, plus code to create them from B/E events, as
   * well as arrange them into subRows.
   *
   * Do not mutate the slices array directly. Modify it only by
   * SliceGroup mutation methods.
   *
   * @constructor
   * @param {function(new:Slice, category, title, colorId, start, args)=}
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
     * @return {Number} The number of slices in this group.
     */
    get length() {
      return this.slices.length;
    },

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
     * Push an instant event into the slice list.
     * @param {tracing.trace_model.InstantEvent} instantEvent The instantEvent.
     */
    pushInstantEvent: function(instantEvent) {
      this.slices.push(instantEvent);
    },

    /**
     * Opens a new slice in the group's slices.
     *
     * Calls to beginSlice and
     * endSlice must be made with non-monotonically-decreasing timestamps.
     *
     * @param {String} title Title of the slice to add.
     * @param {Number} ts The timetsamp of the slice, in milliseconds.
     * @param {Object.<string, Object>=} opt_args Arguments associated with
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

    get mostRecentlyOpenedPartialSlice() {
      if (!this.openPartialSlices_.length)
        return undefined;
      return this.openPartialSlices_[this.openPartialSlices_.length - 1];
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
        throw new Error('Slice ' + slice.title +
                        ' end time is before its start.');

      slice.duration = ts - slice.start;
      this.pushSlice(slice);

      return slice;
    },

    /**
     * Closes any open slices.
     * @param {Number=} opt_maxTimestamp The end time to use for the closed
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
    },

    copySlice: function(slice) {
      var newSlice = new this.sliceConstructor(slice.category, slice.title,
          slice.colorId, slice.start,
          slice.args, slice.duration);
      newSlice.didNotFinish = slice.didNotFinish;
      return newSlice;
    }
  };

  /**
   * Merge two slice groups.
   *
   * If the two groups do not nest properly some of the slices of groupB will
   * be split to accomodate the improper nesting.  This is done to accomodate
   * combined kernel and userland call stacks on Android.  Because userland
   * tracing is done by writing to the trace_marker file, the kernel calls
   * that get invoked as part of that write may not be properly nested with
   * the userland call trace.  For example the following sequence may occur:
   *
   *     kernel enter sys_write        (the write to trace_marker)
   *     user   enter some_function
   *     kernel exit  sys_write
   *     ...
   *     kernel enter sys_write        (the write to trace_marker)
   *     user   exit  some_function
   *     kernel exit  sys_write
   *
   * This is handled by splitting the sys_write call into two slices as
   * follows:
   *
   *     | sys_write |            some_function            | sys_write (cont.) |
   *                 | sys_write (cont.) |     | sys_write |
   *
   * The colorId of both parts of the split slices are kept the same, and the
   * " (cont.)" suffix is appended to the later parts of a split slice.
   *
   * The two input SliceGroups are not modified by this, and the merged
   * SliceGroup will contain a copy of each of the input groups' slices (those
   * copies may be split).
   */
  SliceGroup.merge = function(groupA, groupB) {
    // This is implemented by traversing the two slice groups in reverse
    // order.  The slices in each group are sorted by ascending end-time, so
    // we must do the traversal from back to front in order to maintain the
    // sorting.
    //
    // We traverse the two groups simultaneously, merging as we go.  At each
    // iteration we choose the group from which to take the next slice based
    // on which group's next slice has the greater end-time.  During this
    // traversal we maintain a stack of currently "open" slices for each input
    // group.  A slice is considered "open" from the time it gets reached in
    // our input group traversal to the time we reach an slice in this
    // traversal with an end-time before the start time of the "open" slice.
    //
    // Each time a slice from groupA is opened or closed (events corresponding
    // to the end-time and start-time of the input slice, respectively) we
    // split all of the currently open slices from groupB.

    if (groupA.openPartialSlices_.length > 0) {
      throw new Error('groupA has open partial slices');
    }
    if (groupB.openPartialSlices_.length > 0) {
      throw new Error('groupB has open partial slices');
    }

    var result = new SliceGroup();

    var slicesA = groupA.slices;
    var slicesB = groupB.slices;
    var idxA = slicesA.length - 1;
    var idxB = slicesB.length - 1;
    var openA = [];
    var openB = [];

    var splitOpenSlices = function(when) {
      for (var i = 0; i < openB.length; i++) {
        var oldSlice = openB[i];
        var oldEnd = oldSlice.end;
        if (when < oldSlice.start || oldEnd < when) {
          throw new Error('slice should not be split');
        }

        var newSlice = result.copySlice(oldSlice);
        oldSlice.start = when;
        oldSlice.duration = oldEnd - when;
        oldSlice.title += ' (cont.)';
        newSlice.duration = when - newSlice.start;
        openB[i] = newSlice;
        result.pushSlice(newSlice);
      }
    };

    var closeOpenSlices = function(upTo) {
      while (openA.length > 0 || openB.length > 0) {
        var nextA = openA[openA.length - 1];
        var nextB = openB[openB.length - 1];
        var startA = nextA && nextA.start;
        var startB = nextB && nextB.start;

        if ((startA === undefined || startA < upTo) &&
            (startB === undefined || startB < upTo)) {
          return;
        }

        if (startB === undefined || startA > startB) {
          splitOpenSlices(startA);
          openA.pop();
        } else {
          openB.pop();
        }
      }
    };

    while (idxA >= 0 || idxB >= 0) {
      var sA = slicesA[idxA];
      var sB = slicesB[idxB];
      var nextSlice, isFromB;

      if (sA === undefined || (sB !== undefined && sA.end < sB.end)) {
        nextSlice = result.copySlice(sB);
        isFromB = true;
        idxB--;
      } else {
        nextSlice = result.copySlice(sA);
        isFromB = false;
        idxA--;
      }

      closeOpenSlices(nextSlice.end);

      result.pushSlice(nextSlice);

      if (isFromB) {
        openB.push(nextSlice);
      } else {
        splitOpenSlices(nextSlice.end);
        openA.push(nextSlice);
      }
    }

    closeOpenSlices();

    result.slices.reverse();

    return result;
  };

  return {
    SliceGroup: SliceGroup
  };
});
