// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineCounter class.
 */
base.defineModule('timeline_counter')
    .dependsOn()
    .exportsTo('tracing', function() {

  /**
   * Stores all the samples for a given counter.
   * @constructor
   */
  function TimelineCounter(parent, id, name) {
    this.parent = parent;
    this.id = id;
    this.name = name;
    this.seriesNames = [];
    this.seriesColors = [];
    this.timestamps = [];
    this.samples = [];
  }

  TimelineCounter.prototype = {
    __proto__: Object.prototype,

    get numSeries() {
      return this.seriesNames.length;
    },

    get numSamples() {
      return this.timestamps.length;
    },

    /**
     * Shifts all the timestamps inside this counter forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var sI = 0; sI < this.timestamps.length; sI++)
        this.timestamps[sI] = (this.timestamps[sI] + amount);
    },

    /**
     * Updates the bounds for this counter based on the samples it contains.
     */
    updateBounds: function() {
      if (this.seriesNames.length != this.seriesColors.length)
        throw new Error('seriesNames.length must match seriesColors.length');
      if (this.numSeries * this.numSamples != this.samples.length)
        throw new Error('samples.length must be a multiple of numSamples.');

      this.totals = [];
      if (this.samples.length == 0) {
        this.minTimestamp = undefined;
        this.maxTimestamp = undefined;
        this.maxTotal = 0;
        return;
      }
      this.minTimestamp = this.timestamps[0];
      this.maxTimestamp = this.timestamps[this.timestamps.length - 1];

      var numSeries = this.numSeries;
      var maxTotal = -Infinity;
      for (var i = 0; i < this.timestamps.length; i++) {
        var total = 0;
        for (var j = 0; j < numSeries; j++) {
          total += this.samples[i * numSeries + j];
          this.totals.push(total);
        }
        if (total > maxTotal)
          maxTotal = total;
      }
      this.maxTotal = maxTotal;
    }

  };

  /**
   * Comparison between counters that orders by pid, then name.
   */
  TimelineCounter.compare = function(x, y) {
    if (x.parent.pid != y.parent.pid) {
      return TimelineProcess.compare(x.parent, y.parent.pid);
    }
    var tmp = x.name.localeCompare(y.name);
    if (tmp == 0)
      return x.tid - y.tid;
    return tmp;
  };

  return {
    TimelineCounter: TimelineCounter,
  }
});