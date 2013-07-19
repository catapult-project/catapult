// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.trace_model_event');

/**
 * @fileoverview Provides the Sample class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A Sample represents a sample taken at an instant in time
   * plus parameters associated with that sample.
   *
   * @constructor
   */
  function Sample(category, title, colorId, start, args) {
    tracing.trace_model.TraceModelEvent.apply(this, arguments);
  }

  Sample.prototype = {
    __proto__: tracing.trace_model.TraceModelEvent.prototype
  };

  return {
    Sample: Sample
  };
});
