// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.guid');
base.require('tracing.trace_model.event');

/**
 * @fileoverview Provides the TimedEvent class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A TimedEvent is the base type for any piece of data in the trace model with
   * a specific start and duration.
   *
   * @constructor
   */
  function TimedEvent(start) {
    tracing.trace_model.Event.call(this);
    this.start = start;
    this.duration = 0;
  }

  TimedEvent.prototype = {
    __proto__: tracing.trace_model.Event.prototype,

    get end() {
      return this.start + this.duration;
    },

    addBoundsToRange: function(range) {
      range.addValue(this.start);
      range.addValue(this.end);
    },

    bounds: function(that) {
      // Due to inaccuracy of floating-point calculation, the end times of
      // slices from a B/E pair (whose end = start + original_end - start)
      // and an X event (whose end = start + duration) at the same time may
      // become not equal. Tolerate 1ps error.
      return this.start <= that.start && this.end - that.end > -1e-9;
    }
  };

  return {
    TimedEvent: TimedEvent
  };
});
