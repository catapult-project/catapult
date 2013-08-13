// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.timed_event');

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
    tracing.trace_model.TimedEvent.call(this, start);

    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.args = args;
  }

  Sample.prototype = {
    __proto__: tracing.trace_model.TimedEvent.prototype
  };

  return {
    Sample: Sample
  };
});
