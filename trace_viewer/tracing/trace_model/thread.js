// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Thread class.
 */
tvcm.require('tvcm.guid');
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.slice');
tvcm.require('tracing.trace_model.slice_group');
tvcm.require('tracing.trace_model.async_slice_group');
tvcm.require('tracing.trace_model.sample');

tvcm.exportTo('tracing.trace_model', function() {

  var Slice = tracing.trace_model.Slice;
  var SliceGroup = tracing.trace_model.SliceGroup;
  var AsyncSlice = tracing.trace_model.AsyncSlice;
  var AsyncSliceGroup = tracing.trace_model.AsyncSliceGroup;

  /**
   * A ThreadSlice represents an interval of time on a thread resource
   * with associated nestinged slice information.
   *
   * ThreadSlices are typically associated with a specific trace event pair on a
   * specific thread.
   * For example,
   *   TRACE_EVENT_BEGIN1("x","myArg", 7) at time=0.1ms
   *   TRACE_EVENT_END0()                 at time=0.3ms
   * This results in a single slice from 0.1 with duration 0.2 on a
   * specific thread.
   *
   * @constructor
   */
  function ThreadSlice(cat, title, colorId, start, args, opt_duration,
                       opt_threadStart, opt_threadDuration) {
    Slice.call(this, cat, title, colorId, start, args, opt_duration,
               opt_threadStart, opt_threadDuration);
    // Do not modify this directly.
    // subSlices is configured by SliceGroup.rebuildSubRows_.
    this.subSlices = [];
  }

  ThreadSlice.prototype = {
    __proto__: Slice.prototype
  };

  /**
   * A Thread stores all the trace events collected for a particular
   * thread. We organize the synchronous slices on a thread by "subrows," where
   * subrow 0 has all the root slices, subrow 1 those nested 1 deep, and so on.
   * The asynchronous slices are stored in an AsyncSliceGroup object.
   *
   * The slices stored on a Thread should be instances of
   * ThreadSlice.
   *
   * @constructor
   */
  function Thread(parent, tid) {
    this.guid_ = tvcm.GUID.allocate();
    if (!parent)
      throw new Error('Parent must be provided.');
    this.parent = parent;
    this.sortIndex = 0;
    this.tid = tid;

    var that = this;
    function ThreadSliceForThisThread(
        cat, title, colorId, start, args, opt_duration,
        opt_threadStart, opt_threadDuration) {
      ThreadSlice.call(this, cat, title, colorId, start, args, opt_duration,
                       opt_threadStart, opt_threadDuration);
      this.parentThread = that;
    }
    ThreadSliceForThisThread.prototype = {
      __proto__: ThreadSlice.prototype
    };

    this.sliceGroup = new SliceGroup(ThreadSliceForThisThread);
    this.timeSlices = undefined;
    this.samples_ = [];
    this.kernelSliceGroup = new SliceGroup();
    this.asyncSliceGroup = new AsyncSliceGroup();
    this.bounds = new tvcm.Range();
    this.ephemeralSettings = {};
  }

  Thread.prototype = {

    /*
     * @return {Number} A globally unique identifier for this counter.
     */
    get guid() {
      return this.guid_;
    },

    compareTo: function(that) {
      return Thread.compare(this, that);
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
     * Adds a new sample in the thread's samples.
     *
     * Calls to addSample must be made with non-monotonically-decreasing
     * timestamps.
     *
     * @param {String} category Category of the sample to add.
     * @param {String} title Title of the sample to add.
     * @param {Number} ts The timetsamp of the sample, in milliseconds.
     * @param {Object.<string, Object>=} opt_args Arguments associated with
     * the sample.
     */
    addSample: function(category, title, ts, opt_args) {
      if (this.samples_.length) {
        var lastSample = this.samples_[this.samples_.length - 1];
        if (ts < lastSample.start) {
          throw new
              Error('Samples must be added in increasing timestamp order.');
        }
      }
      var colorId = tvcm.ui.getStringColorId(title);
      var sample = new tracing.trace_model.Sample(category, title, colorId, ts,
                                                  opt_args ? opt_args : {});
      this.samples_.push(sample);
      return sample;
    },

    /**
     * Returns the array of samples added to this thread. If no samples
     * have been added, an empty array is returned.
     *
     * @return {Array<Sample>} array of samples.
     */
    get samples() {
      return this.samples_;
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
      this.sliceGroup.shiftTimestampsForward(amount);

      if (this.timeSlices) {
        for (var i = 0; i < this.timeSlices.length; i++) {
          var slice = this.timeSlices[i];
          slice.start += amount;
        }
      }

      if (this.samples_.length) {
        for (var i = 0; i < this.samples_.length; i++) {
          var sample = this.samples_[i];
          sample.start += amount;
        }
      }

      this.kernelSliceGroup.shiftTimestampsForward(amount);
      this.asyncSliceGroup.shiftTimestampsForward(amount);
    },

    /**
     * Determines whether this thread is empty. If true, it usually implies
     * that it should be pruned from the model.
     */
    get isEmpty() {
      if (this.sliceGroup.length)
        return false;
      if (this.sliceGroup.openSliceCount)
        return false;
      if (this.timeSlices && this.timeSlices.length)
        return false;
      if (this.kernelSliceGroup.length)
        return false;
      if (this.asyncSliceGroup.length)
        return false;
      if (this.samples_.length)
        return false;
      return true;
    },

    /**
     * Updates the bounds based on the
     * current objects associated with the thread.
     */
    updateBounds: function() {
      this.bounds.reset();

      this.sliceGroup.updateBounds();
      this.bounds.addRange(this.sliceGroup.bounds);

      this.kernelSliceGroup.updateBounds();
      this.bounds.addRange(this.kernelSliceGroup.bounds);

      this.asyncSliceGroup.updateBounds();
      this.bounds.addRange(this.asyncSliceGroup.bounds);

      if (this.timeSlices && this.timeSlices.length) {
        this.bounds.addValue(this.timeSlices[0].start);
        this.bounds.addValue(
            this.timeSlices[this.timeSlices.length - 1].end);
      }
      if (this.samples_.length) {
        this.bounds.addValue(this.samples_[0].start);
        this.bounds.addValue(
            this.samples_[this.samples_.length - 1].end);
      }
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var i = 0; i < this.sliceGroup.length; i++)
        categoriesDict[this.sliceGroup.slices[i].category] = true;
      for (var i = 0; i < this.kernelSliceGroup.length; i++)
        categoriesDict[this.kernelSliceGroup.slices[i].category] = true;
      for (var i = 0; i < this.asyncSliceGroup.length; i++)
        categoriesDict[this.asyncSliceGroup.slices[i].category] = true;
      for (var i = 0; i < this.samples_.length; i++)
        categoriesDict[this.samples_[i].category] = true;
    },

    autoCloseOpenSlices: function(opt_maxTimestamp) {
      this.sliceGroup.autoCloseOpenSlices(opt_maxTimestamp);
      this.kernelSliceGroup.autoCloseOpenSlices(opt_maxTimestamp);
    },

    mergeKernelWithUserland: function() {
      if (this.kernelSliceGroup.length > 0) {
        var newSlices = SliceGroup.merge(
            this.sliceGroup, this.kernelSliceGroup);
        this.sliceGroup.slices = newSlices.slices;
        this.kernelSliceGroup = new SliceGroup();
        this.updateBounds();
      }
    },

    createSubSlices: function() {
      this.sliceGroup.createSubSlices();
    },

    /**
     * @return {String} A user-friendly name for this thread.
     */
    get userFriendlyName() {
      return this.name || this.tid;
    },

    /**
     * @return {String} User friendly details about this thread.
     */
    get userFriendlyDetails() {
      return 'tid: ' + this.tid +
          (this.name ? ', name: ' + this.name : '');
    },

    getSettingsKey: function() {
      if (!this.name)
        return undefined;
      var parentKey = this.parent.getSettingsKey();
      if (!parentKey)
        return undefined;
      return parentKey + '.' + this.name;
    },

    /*
     * Returns the index of the slice in the timeSlices array, or undefined.
     */
    indexOfTimeSlice: function(timeSlice) {
      var i = tvcm.findLowIndexInSortedArray(
          this.timeSlices,
          function(slice) { return slice.start; },
          timeSlice.start);
      if (this.timeSlices[i] !== timeSlice)
        return undefined;
      return i;
    },

    iterateAllEvents: function(callback, opt_this) {
      this.sliceGroup.iterateAllEvents(callback, opt_this);
      this.kernelSliceGroup.iterateAllEvents(callback, opt_this);
      this.asyncSliceGroup.iterateAllEvents(callback, opt_this);

      if (this.timeSlices && this.timeSlices.length)
        this.timeSlices.forEach(callback, opt_this);

      this.samples_.forEach(callback, opt_this);
    }
  };

  /**
   * Comparison between threads that orders first by parent.compareTo,
   * then by names, then by tid.
   */
  Thread.compare = function(x, y) {
    var tmp = x.parent.compareTo(y.parent);
    if (tmp)
      return tmp;

    tmp = x.sortIndex - y.sortIndex;
    if (tmp)
      return tmp;

    tmp = tvcm.comparePossiblyUndefinedValues(
        x.name, y.name,
        function(x, y) { return x.localeCompare(y); });
    if (tmp)
      return tmp;

    return x.tid - y.tid;
  };

  return {
    ThreadSlice: ThreadSlice,
    Thread: Thread
  };
});
