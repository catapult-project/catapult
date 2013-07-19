// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.trace_model_event');

/**
 * @fileoverview Provides the Slice class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A Slice represents an interval of time plus parameters associated
   * with that interval.
   *
   * @constructor
   */
  function Slice(category, title, colorId, start, args, opt_duration) {
    tracing.trace_model.TraceModelEvent.
        call(this, category, title, colorId, start, args);

    if (opt_duration !== undefined)
      this.duration = opt_duration;
  }

  Slice.prototype = {
    __proto__: tracing.trace_model.TraceModelEvent.prototype,

    get end() {
      return this.start + this.duration;
    }
  };

  return {
    Slice: Slice
  };
});
