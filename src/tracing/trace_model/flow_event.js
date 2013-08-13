// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.timed_event');

/**
 * @fileoverview Provides the Flow class.
 */
base.exportTo('tracing.trace_model', function() {
  /**
   * A Flow represents an interval of time plus parameters associated
   * with that interval.
   *
   * @constructor
   */
  function FlowEvent(category, id, title, colorId, start, args) {
    tracing.trace_model.TimedEvent.call(this, start);

    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.start = start;
    this.args = args;

    this.id = id;
  }

  FlowEvent.prototype = {
    __proto__: tracing.trace_model.TimedEvent.prototype
  };

  return {
    FlowEvent: FlowEvent
  };
});
