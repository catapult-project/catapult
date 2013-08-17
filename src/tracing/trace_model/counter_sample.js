// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
base.require('base.iteration_helpers');
base.require('base.sorted_array_utils');
base.require('tracing.trace_model.event');

base.exportTo('tracing.trace_model', function() {
  function CounterSample(series, timestamp, value) {
    tracing.trace_model.Event.call(this);
    this.series_ = series;
    this.timestamp_ = timestamp;
    this.value_ = value;
  }

  CounterSample.groupByTimestamp = function(samples) {
    var samplesByTimestamp = {};
    for (var i = 0; i < samples.length; i++) {
      var sample = samples[i];
      var ts = sample.timestamp;
      if (!samplesByTimestamp[ts])
        samplesByTimestamp[ts] = [];
      samplesByTimestamp[ts].push(sample);
    }
    var timestamps = base.dictionaryKeys(samplesByTimestamp);
    timestamps.sort();
    var groups = [];
    for (var i = 0; i < timestamps.length; i++) {
      var ts = timestamps[i];
      var group = samplesByTimestamp[ts];
      group.sort(function(x, y) {
        return x.series.seriesIndex - y.series.seriesIndex;
      });
      groups.push(group);
    }
    return groups;
  }

  CounterSample.prototype = {
    __proto__: tracing.trace_model.Event.prototype,

    get series() {
      return this.series_;
    },

    get timestamp() {
      return this.timestamp_;
    },

    get value() {
      return this.value_;
    },

    set timestamp(timestamp) {
      this.timestamp_ = timestamp;
    },

    addBoundsToRange: function(range) {
      range.addValue(this.timestamp);
    },

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'series_') {
          obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    getSampleIndex: function() {
      return base.findLowIndexInSortedArray(
          this.series.timestamps,
          function(x) { return x; },
          this.timestamp_);
    }
  };

  return {
    CounterSample: CounterSample
  };
});
