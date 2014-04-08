// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Quick range computations.
 */
tvcm.exportTo('tvcm', function() {

  function Range() {
    this.isEmpty_ = true;
    this.min_ = undefined;
    this.max_ = undefined;
  };

  Range.prototype = {
    __proto__: Object.prototype,

    reset: function() {
      this.isEmpty_ = true;
      this.min_ = undefined;
      this.max_ = undefined;
    },

    get isEmpty() {
      return this.isEmpty_;
    },

    addRange: function(range) {
      if (range.isEmpty)
        return;
      this.addValue(range.min);
      this.addValue(range.max);
    },

    addValue: function(value) {
      if (this.isEmpty_) {
        this.max_ = value;
        this.min_ = value;
        this.isEmpty_ = false;
        return;
      }
      this.max_ = Math.max(this.max_, value);
      this.min_ = Math.min(this.min_, value);
    },

    set min(min) {
      this.isEmpty_ = false;
      this.min_ = min;
    },

    get min() {
      if (this.isEmpty_)
        return undefined;
      return this.min_;
    },

    get max() {
      if (this.isEmpty_)
        return undefined;
      return this.max_;
    },

    set max(max) {
      this.isEmpty_ = false;
      this.max_ = max;
    },

    get range() {
      if (this.isEmpty_)
        return undefined;
      return this.max_ - this.min_;
    },

    get center() {
      return (this.min_ + this.max_) * 0.5;
    },

    equals: function(that) {
      if (this.isEmpty && that.isEmpty)
        return true;
      if (this.isEmpty != that.isEmpty)
        return false;
      return this.min === that.min &&
          this.max === that.max;
    },

    containsRange: function(range) {
      if (this.isEmpty || range.isEmpty)
        return false;
      return this.min <= range.min && this.max >= range.max;
    },

    containsExplicitRange: function(min, max) {
      if (this.isEmpty)
        return false;
      return this.min <= min && this.max >= max;
    },

    intersectsRange: function(range) {
      if (this.isEmpty || range.isEmpty)
        return false;
      return !(range.max < this.min ||
               range.min > this.max);
    }
  };

  Range.compareByMinTimes = function(a, b) {
    if (!a.isEmpty && !b.isEmpty)
      return a.min_ - b.min_;

    if (a.isEmpty && !b.isEmpty)
      return -1;

    if (!a.isEmpty && b.isEmpty)
      return 1;

    return 0;
  };

  return {
    Range: Range
  };

});
