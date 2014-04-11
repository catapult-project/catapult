// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Cpu class.
 */
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.slice');
tvcm.require('tracing.trace_model.counter');
tvcm.exportTo('tracing.trace_model', function() {

  var Counter = tracing.trace_model.Counter;
  var Slice = tracing.trace_model.Slice;

  /**
   * A CpuSlice represents a slice of time on a CPU.
   *
   * @constructor
   */
  function CpuSlice(cat, title, colorId, start, args, opt_duration) {
    Slice.apply(this, arguments);
    this.threadThatWasRunning = undefined;
    this.cpu = undefined;
  }

  CpuSlice.prototype = {
    __proto__: Slice.prototype,

    get analysisTypeName() {
      return 'tracing.analysis.CpuSlice';
    },

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'cpu' || key == 'threadThatWasRunning') {
          if (this[key])
            obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    getAssociatedTimeslice: function() {
      if (!this.threadThatWasRunning)
        return undefined;
      var timeSlices = this.threadThatWasRunning.timeSlices;
      for (var i = 0; i < timeSlices.length; i++) {
        var timeSlice = timeSlices[i];
        if (timeSlice.start !== this.start)
          continue;
        if (timeSlice.duration !== this.duration)
          continue;
        return timeSlice;
      }
      return undefined;
    }
  };

  /**
   * A ThreadTimeSlice is a slice of time on a specific thread where that thread
   * was running on a specific CPU, or in a specific sleep state.
   *
   * As a thread switches moves through its life, it sometimes goes to sleep and
   * can't run. Other times, its runnable but isn't actually assigned to a CPU.
   * Finally, sometimes it gets put on a CPU to actually execute. Each of these
   * states is represented by a ThreadTimeSlice:
   *
   *   Sleeping or runnable: cpuOnWhichThreadWasRunning is undefined
   *   Running:  cpuOnWhichThreadWasRunning is set.
   *
   * @constructor
   */
  function ThreadTimeSlice(
      thread, cat, title, colorId, start, args, opt_duration) {
    Slice.call(this, cat, title, colorId, start, args, opt_duration);
    this.thread = thread;
    this.cpuOnWhichThreadWasRunning = undefined;
  }

  ThreadTimeSlice.prototype = {
    __proto__: Slice.prototype,

    get analysisTypeName() {
      return 'tracing.analysis.ThreadTimeSlice';
    },

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'thread' || key == 'cpuOnWhichThreadWasRunning') {
          if (this[key])
            obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    getAssociatedCpuSlice: function() {
      if (!this.cpuOnWhichThreadWasRunning)
        return undefined;
      var cpuSlices = this.cpuOnWhichThreadWasRunning.slices;
      for (var i = 0; i < cpuSlices.length; i++) {
        var cpuSlice = cpuSlices[i];
        if (cpuSlice.start !== this.start)
          continue;
        if (cpuSlice.duration !== this.duration)
          continue;
        return cpuSlice;
      }
      return undefined;
    },

    getCpuSliceThatTookCpu: function() {
      if (this.cpuOnWhichThreadWasRunning)
        return undefined;
      var curIndex = this.thread.indexOfTimeSlice(this);
      var cpuSliceWhenLastRunning;
      while (curIndex >= 0) {
        var curSlice = this.thread.timeSlices[curIndex];
        if (!curSlice.cpuOnWhichThreadWasRunning) {
          curIndex--;
          continue;
        }
        cpuSliceWhenLastRunning = curSlice.getAssociatedCpuSlice();
        break;
      }
      if (!cpuSliceWhenLastRunning)
        return undefined;

      var cpu = cpuSliceWhenLastRunning.cpu;
      var indexOfSliceOnCpuWhenLastRunning =
          cpu.indexOf(cpuSliceWhenLastRunning);
      var nextRunningSlice = cpu.slices[indexOfSliceOnCpuWhenLastRunning + 1];
      if (!nextRunningSlice)
        return undefined;
      if (Math.abs(nextRunningSlice.start - cpuSliceWhenLastRunning.end) <
          0.00001)
        return nextRunningSlice;
      return undefined;
    }
  };

  /**
   * The Cpu represents a Cpu from the kernel's point of view.
   * @constructor
   */
  function Cpu(kernel, number) {
    if (kernel === undefined || number === undefined)
      throw new Error('Missing arguments');
    this.kernel = kernel;
    this.cpuNumber = number;
    this.slices = [];
    this.counters = {};
    this.bounds = new tvcm.Range();
    this.samples_ = undefined; // Set during createSubSlices
  };

  Cpu.prototype = {
    /**
     * @return {TimelineCounter} The counter on this process named 'name',
     * creating it if it doesn't exist.
     */
    getOrCreateCounter: function(cat, name) {
      var id;
      if (cat.length)
        id = cat + '.' + name;
      else
        id = name;
      if (!this.counters[id])
        this.counters[id] = new Counter(this, id, cat, name);
      return this.counters[id];
    },

    /**
     * Shifts all the timestamps inside this CPU forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var sI = 0; sI < this.slices.length; sI++)
        this.slices[sI].start = (this.slices[sI].start + amount);
      for (var id in this.counters)
        this.counters[id].shiftTimestampsForward(amount);
    },

    /**
     * Updates the range based on the current slices attached to the cpu.
     */
    updateBounds: function() {
      this.bounds.reset();
      if (this.slices.length) {
        this.bounds.addValue(this.slices[0].start);
        this.bounds.addValue(this.slices[this.slices.length - 1].end);
      }
      for (var id in this.counters) {
        this.counters[id].updateBounds();
        this.bounds.addRange(this.counters[id].bounds);
      }
      if (this.samples_ && this.samples_.length) {
        this.bounds.addValue(this.samples_[0].start);
        this.bounds.addValue(
            this.samples_[this.samples_.length - 1].end);
      }
    },

    createSubSlices: function() {
      this.samples_ = this.kernel.model.samples.filter(function(sample) {
        return sample.cpu == this;
      }, this);
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var i = 0; i < this.slices.length; i++)
        categoriesDict[this.slices[i].category] = true;
      for (var id in this.counters)
        categoriesDict[this.counters[id].category] = true;
      for (var i = 0; i < this.samples_.length; i++)
        categoriesDict[this.samples_[i].category] = true;
    },

    get userFriendlyName() {
      return 'CPU ' + this.cpuNumber;
    },

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'kernel')
          continue;
        obj[key] = this[key];
      }
      return obj;
    },

    /*
     * Returns the index of the slice in the CPU's slices, or undefined.
     */
    indexOf: function(cpuSlice) {
      var i = tvcm.findLowIndexInSortedArray(
          this.slices,
          function(slice) { return slice.start; },
          cpuSlice.start);
      if (this.slices[i] !== cpuSlice)
        return undefined;
      return i;
    },

    iterateAllEvents: function(callback, opt_this) {
      this.slices.forEach(callback, opt_this);

      for (var id in this.counters)
        this.counters[id].iterateAllEvents(callback, opt_this);
    },

    get samples() {
      return this.samples_;
    }
  };

  /**
   * Comparison between processes that orders by cpuNumber.
   */
  Cpu.compare = function(x, y) {
    return x.cpuNumber - y.cpuNumber;
  };


  return {
    Cpu: Cpu,
    CpuSlice: CpuSlice,
    ThreadTimeSlice: ThreadTimeSlice
  };
});
