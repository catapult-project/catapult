// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.trace_model.counter_sample');

/**
 * @fileoverview Provides the CounterSeries class.
 */
tvcm.exportTo('tracing.trace_model', function() {
  var CounterSample = tracing.trace_model.CounterSample;

  function CounterSeries(name, color) {
    this.guid_ = tvcm.GUID.allocate();

    this.name_ = name;
    this.color_ = color;

    this.timestamps_ = [];
    this.samples_ = [];

    // Set by counter.addSeries
    this.counter = undefined;
    this.seriesIndex = undefined;
  }

  CounterSeries.prototype = {
    __proto__: Object.prototype,

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'counter') {
          obj[key] = this[key].guid;
          continue;
        }
        obj[key] = this[key];
      }
      return obj;
    },

    get length() {
      return this.timestamps_.length;
    },

    get name() {
      return this.name_;
    },

    get color() {
      return this.color_;
    },

    get samples() {
      return this.samples_;
    },

    get timestamps() {
      return this.timestamps_;
    },

    getSample: function(idx) {
      return this.samples_[idx];
    },

    getTimestamp: function(idx) {
      return this.timestamps_[idx];
    },

    addSample: function(ts, val) {
      this.timestamps_.push(ts);
      var sample = new CounterSample(this, ts, val);
      this.samples_.push(sample);
      return sample;
    },

    getStatistics: function(sampleIndices) {
      var sum = 0;
      var min = Number.MAX_VALUE;
      var max = -Number.MAX_VALUE;

      for (var i = 0; i < sampleIndices.length; ++i) {
        var sample = this.getSample(sampleIndices[i]).value;

        sum += sample;
        min = Math.min(sample, min);
        max = Math.max(sample, max);
      }

      return {
        min: min,
        max: max,
        avg: (sum / sampleIndices.length),
        start: this.getSample(sampleIndices[0]).value,
        end: this.getSample(sampleIndices.length - 1).value
      };
    },

    shiftTimestampsForward: function(amount) {
      for (var i = 0; i < this.timestamps_.length; ++i) {
        this.timestamps_[i] += amount;
        this.samples_[i].timestamp = this.timestamps_[i];
      }
    },

    iterateAllEvents: function(callback, opt_this) {
      this.samples_.forEach(callback, opt_this);
    }
  };

  return {
    CounterSeries: CounterSeries
  };
});
