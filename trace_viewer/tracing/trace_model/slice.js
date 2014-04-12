// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.trace_model.timed_event');

/**
 * @fileoverview Provides the Slice class.
 */
tvcm.exportTo('tracing.trace_model', function() {
  /**
   * A Slice represents an interval of time plus parameters associated
   * with that interval.
   *
   * @constructor
   */
  function Slice(category, title, colorId, start, args, opt_duration,
                 opt_cpuStart, opt_cpuDuration) {
    tracing.trace_model.TimedEvent.call(this, start);

    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.args = args;
    this.didNotFinish = false;

    if (opt_duration !== undefined)
      this.duration = opt_duration;

    if (opt_cpuStart !== undefined)
      this.cpuStart = opt_cpuStart;

    if (opt_cpuDuration !== undefined)
      this.cpuDuration = opt_cpuDuration;
  }

  Slice.prototype = {
    __proto__: tracing.trace_model.TimedEvent.prototype,

    get analysisTypeName() {
      return this.title;
    }
  };

  return {
    Slice: Slice
  };
});
