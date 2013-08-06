// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.trace_model_event');

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
    tracing.trace_model.TraceModelEvent.
        call(this, category, title, colorId, start, args);

    this.id = id;
    this.nextEvent_ = undefined;
    this.prevEvent_ = undefined;
  }

  FlowEvent.prototype = {
    __proto__: tracing.trace_model.TraceModelEvent.prototype,

    set nextEvent(event) {
      this.nextEvent_ = event;
    },

    set prevEvent(event) {
      this.prevEvent_ = event;
    },

    get nextEvent() {
      return this.nextEvent_;
    },

    get prevEvent() {
      return this.prevEvent_;
    },

    isFlowStart: function() {
      return (this.prevEvent_ === undefined);
    },

    isFlowEnd: function() {
      return (this.nextEvent_ === undefined);
    }
  };

  return {
    FlowEvent: FlowEvent
  };
});

