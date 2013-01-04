// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineCpu class.
 */
base.require('range');
base.require('timeline_slice');
base.require('timeline_counter');
base.exportTo('tracing', function() {

  var TimelineCounter = tracing.TimelineCounter;

  /**
   * The TimelineCpu represents a Cpu from the kernel's point of view.
   * @constructor
   */
  function TimelineCpu(number) {
    this.cpuNumber = number;
    this.slices = [];
    this.counters = {};
    this.bounds = new base.Range();
  };

  TimelineCpu.prototype = {
    /**
     * @return {TimlineCounter} The counter on this process named 'name',
     * creating it if it doesn't exist.
     */
    getOrCreateCounter: function(cat, name) {
      var id;
      if (cat.length)
        id = cat + '.' + name;
      else
        id = name;
      if (!this.counters[id])
        this.counters[id] = new TimelineCounter(this, id, cat, name);
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
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var i = 0; i < this.slices.length; i++)
        categoriesDict[this.slices[i].category] = true;
      for (var id in this.counters)
        categoriesDict[this.counters[id].category] = true;
    },

  };

  /**
   * Comparison between processes that orders by cpuNumber.
   */
  TimelineCpu.compare = function(x, y) {
    return x.cpuNumber - y.cpuNumber;
  };


  return {
    TimelineCpu: TimelineCpu
  };
});
