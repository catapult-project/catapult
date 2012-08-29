// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineThread class.
 */
base.require('timeline_slice');
base.require('timeline_slice_group');
base.require('timeline_async_slice_group');
base.exportTo('tracing', function() {

  var TimelineSlice = tracing.TimelineSlice;
  var TimelineSliceGroup = tracing.TimelineSliceGroup;
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
  function TimelineThreadSlice(cat, title, colorId, start, args, opt_duration) {
    TimelineSlice.call(this, cat, title, colorId, start, args, opt_duration);
    // Do not modify this directly.
    // subSlices is configured by TimelineSliceGroup.rebuildSubRows_.
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
    TimelineSliceGroup.call(this, TimelineThreadSlice);
    if (!parent)
      throw new Error('Parent must be provided.');
    this.pid = parent.pid;
    this.tid = tid;
    this.cpuSlices = undefined;
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

    __proto__: TimelineSliceGroup.prototype,

    /**
     * Name of the thread, if present.
     */
    name: undefined,

    /**
     * @return {string} A concatenation of the pid and the thread's
     * tid. Can be used to uniquely identify a thread.
     */
    get ptid() {
      return TimelineThread.getPTIDFromPidAndTid(this.tid, this.pid);
    },

    /**
     * Shifts all the timestamps inside this thread forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      TimelineSliceGroup.prototype.shiftTimestampsForward.call(this, amount);

      if (this.cpuSlices) {
        for (var i = 0; i < this.cpuSlices.length; i++) {
          var slice = this.cpuSlices[i];
          slice.start += amount;
        }
      }

      this.asyncSlices.shiftTimestampsForward(amount);
    },

    /**
     * Determins whether this thread is empty. If true, it usually implies
     * that it should be pruned from the model.
     */
    get isEmpty() {
      if (this.slices.length)
        return false;
      if (this.openSliceCount)
        return false;
      if (this.cpuSlices && this.cpuSlices.length)
        return false;
      if (this.asyncSlices.length)
        return false;
      return true;
    },

    /**
     * Updates the minTimestamp and maxTimestamp fields based on the
     * current objects associated with the thread.
     */
    updateBounds: function() {
      TimelineSliceGroup.prototype.updateBounds.call(this);
      var values = [];
      if (this.minTimestamp !== undefined)
        values.push(this.minTimestamp, this.maxTimestamp);

      if (this.asyncSlices.slices.length) {
        this.asyncSlices.updateBounds();
        values.push(this.asyncSlices.minTimestamp);
        values.push(this.asyncSlices.maxTimestamp);
      }

      if (this.cpuSlices && this.cpuSlices.length) {
        values.push(this.cpuSlices[0].start);
        values.push(this.cpuSlices[this.cpuSlices.length - 1].end);
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
      return this.pid + ': ' + tname;
    },

    /**
     * @return {String} User friendly details about this thread.
     */
    get userFriendlyDetails() {
      return 'pid: ' + this.pid +
          ', tid: ' + this.tid +
          (this.name ? ', name: ' + this.name : '');
    }
  };

  /**
   * Comparison between threads that orders first by pid,
   * then by names, then by tid.
   */
  TimelineThread.compare = function(x, y) {
    if (x.pid != y.pid)
      return x.pid - y.pid;

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
  };
});
