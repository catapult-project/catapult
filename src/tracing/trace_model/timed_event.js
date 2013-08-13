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
    this.guid_ = base.GUID.allocate();
    this.start = start;
    this.duration = 0;
  }

  TimedEvent.prototype = {
    __proto__: tracing.trace_model.Event.prototype,

    get end() {
      return this.start + this.duration;
    }
  };

  return {
    TimedEvent: TimedEvent
  };
});
