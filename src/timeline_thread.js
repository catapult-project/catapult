// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineThread class.
 */
base.defineModule('timeline_thread')
    .dependsOn('timeline_slice',
               'timeline_async_slice_group')
    .exportsTo('tracing', function() {

  var TimelineSlice = tracing.TimelineSlice;
  var TimelineAsyncSlice = tracing.TimelineAsyncSlice;
  var TimelineAsyncSliceGroup = tracing.TimelineAsyncSliceGroup;

  /**
   * A TimelineThreadSlice represents an interval of time on a thread resource
   * with associated nestinged slice information.
   *
   * ThreadSlices are typically associated with a specific trace event pair on a
   * specific thread.
   * For example,
   *   TRACE_EVENT_BEGIN1("x","myArg", 7) at time=0.1ms
   *   TRACE_EVENT_END0()                 at time=0.3ms
   * This results in a single timeline slice from 0.1 with duration 0.2 on a
   * specific thread.
   *
   * @constructor
   */
  function TimelineThreadSlice(title, colorId, start, args, opt_duration) {
    TimelineSlice.call(this, title, colorId, start, args, opt_duration);
    this.subSlices = [];
  }

  TimelineThreadSlice.prototype = {
    __proto__: TimelineSlice.prototype
  };

  /**
   * A TimelineThread stores all the trace events collected for a particular
   * thread. We organize the synchronous slices on a thread by "subrows," where
   * subrow 0 has all the root slices, subrow 1 those nested 1 deep, and so on.
   * The asynchronous slices are stored in an TimelineAsyncSliceGroup object.
   *
   * The slices stored on a TimelineThread should be instances of
   * TimelineThreadSlice.
   *
   * @constructor
   */
  function TimelineThread(parent, tid) {
    if (!parent)
      throw new Error('Parent must be provided.');
    this.parent = parent;
    this.tid = tid;
    this.subRows = [[]];
    this.asyncSlices = new TimelineAsyncSliceGroup(this.ptid);
  }

  var ptidMap = {};

  /**
   * @return {String} A string that can be used as a unique key for a specific
   * thread within a process.
   */
  TimelineThread.getPTIDFromPidAndTid = function(pid, tid) {
    if (!ptidMap[pid])
      ptidMap[pid] = {};
    if (!ptidMap[pid][tid])
      ptidMap[pid][tid] = pid + ':' + tid;
    return ptidMap[pid][tid];
  }

  TimelineThread.prototype = {
    /**
     * Name of the thread, if present.
     */
    name: undefined,

    /**
     * @return {string} A concatenation of the parent id and the thread's
     * tid. Can be used to uniquely identify a thread.
     */
    get ptid() {
      return TimelineThread.getPTIDFromPidAndTid(this.tid, this.parent.pid);
    },

    getSubrow: function(i) {
      while (i >= this.subRows.length)
        this.subRows.push([]);
      return this.subRows[i];
    },


    shiftSubRow_: function(subRow, amount) {
      for (var tS = 0; tS < subRow.length; tS++) {
        var slice = subRow[tS];
        slice.start = (slice.start + amount);
      }
    },

    /**
     * Shifts all the timestamps inside this thread forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      if (this.cpuSlices)
        this.shiftSubRow_(this.cpuSlices, amount);

      for (var tSR = 0; tSR < this.subRows.length; tSR++) {
        this.shiftSubRow_(this.subRows[tSR], amount);
      }

      this.asyncSlices.shiftTimestampsForward(amount);
    },

    /**
     * Updates the minTimestamp and maxTimestamp fields based on the
     * current objects associated with the thread.
     */
    updateBounds: function() {
      var values = [];
      var slices;
      if (this.subRows[0].length != 0) {
        slices = this.subRows[0];
        values.push(slices[0].start);
        values.push(slices[slices.length - 1].end);
      }
      if (this.asyncSlices.slices.length) {
        this.asyncSlices.updateBounds();
        values.push(this.asyncSlices.minTimestamp);
        values.push(this.asyncSlices.maxTimestamp);
      }
      if (values.length) {
        this.minTimestamp = Math.min.apply(Math, values);
        this.maxTimestamp = Math.max.apply(Math, values);
      } else {
        this.minTimestamp = undefined;
        this.maxTimestamp = undefined;
      }
    },

    /**
     * @return {String} A user-friendly name for this thread.
     */
    get userFriendlyName() {
      var tname = this.name || this.tid;
      return this.parent.pid + ': ' + tname;
    },

    /**
     * @return {String} User friendly details about this thread.
     */
    get userFriendlyDetails() {
      return 'pid: ' + this.parent.pid +
          ', tid: ' + this.tid +
          (this.name ? ', name: ' + this.name : '');
    }
  };

  /**
   * Comparison between threads that orders first by pid,
   * then by names, then by tid.
   */
  TimelineThread.compare = function(x, y) {
    if (x.parent.pid != y.parent.pid) {
      return tracing.TimelineProcess.compare(x.parent, y.parent.pid);
    }

    if (x.name && y.name) {
      var tmp = x.name.localeCompare(y.name);
      if (tmp == 0)
        return x.tid - y.tid;
      return tmp;
    } else if (x.name) {
      return -1;
    } else if (y.name) {
      return 1;
    } else {
      return x.tid - y.tid;
    }
  };

  return {
    TimelineThreadSlice: TimelineThreadSlice,
    TimelineThread: TimelineThread
  }
});