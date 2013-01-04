// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineThread class.
 */
base.require('range');
base.require('timeline_guid');
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
    this.guid_ = tracing.GUID.allocate();
    if (!parent)
      throw new Error('Parent must be provided.');
    this.parent = parent;
    this.tid = tid;
    this.cpuSlices = undefined;
    this.asyncSlices = new TimelineAsyncSliceGroup();
    this.bounds = new base.Range();
  }

  TimelineThread.prototype = {

    __proto__: TimelineSliceGroup.prototype,

    /*
     * @return {Number} A globally unique identifier for this counter.
     */
    get guid() {
      return this.guid_;
    },

    compareTo: function(that) {
      return TimelineThread.compare(this, that);
    },

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'parent') {
          obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    /**
     * Name of the thread, if present.
     */
    name: undefined,

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
     * Updates the bounds based on the
     * current objects associated with the thread.
     */
    updateBounds: function() {
      TimelineSliceGroup.prototype.updateBounds.call(this);

      this.asyncSlices.updateBounds();
      this.bounds.addRange(this.asyncSlices.bounds);

      if (this.cpuSlices && this.cpuSlices.length) {
        this.bounds.addValue(this.cpuSlices[0].start);
        this.bounds.addValue(
          this.cpuSlices[this.cpuSlices.length - 1].end);
      }
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var i = 0; i < this.slices.length; i++)
        categoriesDict[this.slices[i].category] = true;
      for (var i = 0; i < this.asyncSlices.length; i++)
        categoriesDict[this.asyncSlices.slices[i].category] = true;
    },

    /**
     * @return {String} A user-friendly name for this thread.
     */
    get userFriendlyName() {
      var tname = this.name || this.tid;
      return this.parent.userFriendlyName + ': ' + tname;
    },

    /**
     * @return {String} User friendly details about this thread.
     */
    get userFriendlyDetails() {
      return this.parent.userFriendlyDetails +
          ', tid: ' + this.tid +
          (this.name ? ', name: ' + this.name : '');
    }
  };

  /**
   * Comparison between threads that orders first by parent.compareTo,
   * then by names, then by tid.
   */
  TimelineThread.compare = function(x, y) {
    var tmp = x.parent.compareTo(y.parent);
    if (tmp != 0)
      return tmp;

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
