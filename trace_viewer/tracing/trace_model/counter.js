// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.guid');
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.counter_series');

/**
 * @fileoverview Provides the Counter class.
 */
tvcm.exportTo('tracing.trace_model', function() {

  /**
   * Stores all the samples for a given counter.
   * @constructor
   */
  function Counter(parent, id, category, name) {
    this.guid_ = tvcm.GUID.allocate();

    this.parent = parent;
    this.id = id;
    this.category = category || '';
    this.name = name;

    this.series_ = [];
    this.totals = [];
    this.bounds = new tvcm.Range();
  }

  Counter.prototype = {
    __proto__: Object.prototype,

    /*
     * @return {Number} A globally unique identifier for this counter.
     */
    get guid() {
      return this.guid_;
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

    set timestamps(arg) {
      throw new Error('Bad counter API. No cookie.');
    },

    set seriesNames(arg) {
      throw new Error('Bad counter API. No cookie.');
    },

    set seriesColors(arg) {
      throw new Error('Bad counter API. No cookie.');
    },

    set samples(arg) {
      throw new Error('Bad counter API. No cookie.');
    },

    addSeries: function(series) {
      series.counter = this;
      series.seriesIndex = this.series_.length;
      this.series_.push(series);
      return series;
    },

    getSeries: function(idx) {
      return this.series_[idx];
    },

    get series() {
      return this.series_;
    },

    get numSeries() {
      return this.series_.length;
    },

    get numSamples() {
      if (this.series_.length === 0)
        return 0;
      return this.series_[0].length;
    },

    get timestamps() {
      if (this.series_.length === 0)
        return [];
      return this.series_[0].timestamps;
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

      var ret = [];
      this.series_.forEach(function(series) {
        ret.push(series.getStatistics(sampleIndices));
      });
      return ret;
    },

    /**
     * Shifts all the timestamps inside this counter forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var i = 0; i < this.series_.length; ++i)
        this.series_[i].shiftTimestampsForward(amount);
    },

    /**
     * Updates the bounds for this counter based on the samples it contains.
     */
    updateBounds: function() {
      this.totals = [];
      this.maxTotal = 0;
      this.bounds.reset();

      if (this.series_.length === 0)
        return;

      var firstSeries = this.series_[0];
      var lastSeries = this.series_[this.series_.length - 1];

      this.bounds.addValue(firstSeries.getTimestamp(0));
      this.bounds.addValue(lastSeries.getTimestamp(lastSeries.length - 1));

      var numSeries = this.numSeries;
      this.maxTotal = -Infinity;

      // Sum the samples at each timestamp.
      // Note, this assumes that all series have all timestamps.
      for (var i = 0; i < firstSeries.length; ++i) {
        var total = 0;
        this.series_.forEach(function(series) {
          total += series.getSample(i).value;
          this.totals.push(total);
        }.bind(this));

        this.maxTotal = Math.max(total, this.maxTotal);
      }
    },

    iterateAllEvents: function(callback, opt_this) {
      for (var i = 0; i < this.series_.length; i++)
        this.series_[i].iterateAllEvents(callback, opt_this);
    }
  };

  /**
   * Comparison between counters that orders by parent.compareTo, then name.
   */
  Counter.compare = function(x, y) {
    var tmp = x.parent.compareTo(y);
    if (tmp != 0)
      return tmp;
    var tmp = x.name.localeCompare(y.name);
    if (tmp == 0)
      return x.tid - y.tid;
    return tmp;
  };

  return {
    Counter: Counter
  };
});
