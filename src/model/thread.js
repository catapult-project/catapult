// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Thread class.
 */
base.require('range');
base.require('guid');
base.require('model.slice');
base.require('model.slice_group');
base.require('model.async_slice_group');
base.require('model.sample');
base.exportTo('tracing.model', function() {

  var Slice = tracing.model.Slice;
  var SliceGroup = tracing.model.SliceGroup;
  var AsyncSlice = tracing.model.AsyncSlice;
  var AsyncSliceGroup = tracing.model.AsyncSliceGroup;

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
  function ThreadSlice(cat, title, colorId, start, args, opt_duration) {
    Slice.call(this, cat, title, colorId, start, args, opt_duration);
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
    SliceGroup.call(this, ThreadSlice);
    this.guid_ = tracing.GUID.allocate();
    if (!parent)
      throw new Error('Parent must be provided.');
    this.parent = parent;
    this.tid = tid;
    this.cpuSlices = undefined;
    this.samples_ = [];
    this.kernelSlices = new SliceGroup();
    this.asyncSlices = new AsyncSliceGroup();
    this.bounds = new base.Range();
  }

  Thread.prototype = {

    __proto__: SliceGroup.prototype,

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
     * @param {Object.<string, Object>} opt_args Arguments associated with
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
      var colorId = tracing.getStringColorId(title);
      var sample = new tracing.model.Sample(category, title, colorId, ts,
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
      SliceGroup.prototype.shiftTimestampsForward.call(this, amount);

      if (this.cpuSlices) {
        for (var i = 0; i < this.cpuSlices.length; i++) {
          var slice = this.cpuSlices[i];
          slice.start += amount;
        }
      }

      if (this.samples_.length) {
        for (var i = 0; i < this.samples_.length; i++) {
          var sample = this.samples_[i];
          sample.start += amount;
        }
      }

      this.kernelSlices.shiftTimestampsForward(amount);
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
      if (this.kernelSlices.length)
        return false;
      if (this.asyncSlices.length)
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
      SliceGroup.prototype.updateBounds.call(this);

      this.kernelSlices.updateBounds();
      this.bounds.addRange(this.kernelSlices.bounds);

      this.asyncSlices.updateBounds();
      this.bounds.addRange(this.asyncSlices.bounds);

      if (this.cpuSlices && this.cpuSlices.length) {
        this.bounds.addValue(this.cpuSlices[0].start);
        this.bounds.addValue(
          this.cpuSlices[this.cpuSlices.length - 1].end);
      }
      if (this.samples_.length) {
        this.bounds.addValue(this.samples_[0].start);
        this.bounds.addValue(
          this.samples_[this.samples_.length - 1].end);
      }
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var i = 0; i < this.slices.length; i++)
        categoriesDict[this.slices[i].category] = true;
      for (var i = 0; i < this.kernelSlices.length; i++)
        categoriesDict[this.kernelSlices.slices[i].category] = true;
      for (var i = 0; i < this.asyncSlices.length; i++)
        categoriesDict[this.asyncSlices.slices[i].category] = true;
      for (var i = 0; i < this.samples_.length; i++)
        categoriesDict[this.samples_[i].category] = true;
    },

    mergeKernelWithUserland: function() {
      if (this.kernelSlices.length > 0) {
        var newSlices = SliceGroup.merge(this, this.kernelSlices);
        this.slices = newSlices.slices;
        this.kernelSlices = new SliceGroup();
        this.updateBounds();
      }
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
  Thread.compare = function(x, y) {
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
    ThreadSlice: ThreadSlice,
    Thread: Thread
  };
});
