// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineCounter class.
 */
base.exportTo('tracing', function() {

  var nextCounterGUID = 1;

  /**
   * Stores all the samples for a given counter.
   * @constructor
   */
  function TimelineCounter(parent, id, category, name) {
    if (parent == null) {
      this.parent_id = null;
    } else if (parent.pid != undefined) {
      this.parent_id = parent.pid;
    } else if (parent.cpuNumber != undefined) {
      this.parent_id = parent.cpuNumber;
    }
    this.id = id;
    this.category = category || '';
    this.name = name;
    this.seriesNames = [];
    this.seriesColors = [];
    this.timestamps = [];
    this.samples = [];
    this.guid_ = nextCounterGUID++;
  }

  TimelineCounter.prototype = {
    __proto__: Object.prototype,
    /*
     * @return {Number} A globally unique identifier for this counter.
     */
    get guid() {
      return this.guid_;
    },

    get numSeries() {
      return this.seriesNames.length;
    },

    get numSamples() {
      return this.timestamps.length;
    },

    getSampleValue: function(index, seriesIndex) {
      return this.samples[index * this.numSeries + seriesIndex];
    },

    /**
     * Obtains min, max, avg, values, start, and end for different series for
     * a given counter
     *     getSampleStatistics([0,1])
     * The statistics objects that this returns are an array of objects, one
     * object for each series for the counter in the form:
     * {min: minVal, max: maxVal, avg: avgVal, start: startVal, end: endVal}
     *
     * @param {Array.<Number>} Indices to summarize.
     * @return {Object} An array of statistics. Each element in the array
     * has data for one of the series in the selected counter.
     */
    getSampleStatistics: function(sampleIndices) {
      sampleIndices.sort();
      var sampleIndex = this.sampleIndex;
      var numSeries = this.numSeries;
      var numSamples = this.numSamples;

      var ret = [];

      for (var i = 0; i < numSeries; ++i) {
        var sum = 0;
        var min = Number.MAX_VALUE;
        var max = -Number.MAX_VALUE;
        for (var j = 0; j < sampleIndices.length; j++) {
          var x = sampleIndices[j];
          sum += this.getSampleValue(x, i);
          min = Math.min(this.getSampleValue(x, i), min);
          max = Math.max(this.getSampleValue(x, i), max);
        }
        var avg = sum / sampleIndices.length;
        var start = this.getSampleValue(sampleIndices[0], i);
        var end = this.getSampleValue(
            sampleIndices[sampleIndices.length - 1], i);

        ret.push({min: min,
          max: max,
          avg: avg,
          start: start,
          end: end});
      }
      return ret;
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
   * Comparison between counters that orders by parent_id, then name.
   */
  TimelineCounter.compare = function(x, y) {
    if (x.parent_id != y.parent_id) {
      return x.parent_id - y.parent_id;
    }
    var tmp = x.name.localeCompare(y.name);
    if (tmp == 0)
      return x.tid - y.tid;
    return tmp;
  };

  return {
    TimelineCounter: TimelineCounter
  };
});
