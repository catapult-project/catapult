// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.trace_model.timed_event');

/**
 * @fileoverview Provides the Sample class.
 */
tvcm.exportTo('tracing.trace_model', function() {
  /**
   * A Sample represents a sample taken at an instant in time, plus its stack
   * frame and parameters associated with that sample.
   *
   * @constructor
   */
  function Sample(cpu, thread, title, start, leafStackFrame,
                  opt_weight, opt_args) {
    tracing.trace_model.TimedEvent.call(this, start);

    this.title = title;
    this.cpu = cpu;
    this.thread = thread;
    this.leafStackFrame = leafStackFrame;
    this.weight = opt_weight;
    this.args = opt_args || {};
  }

  Sample.prototype = {
    __proto__: tracing.trace_model.TimedEvent.prototype,

    get colorId() {
      return this.leafStackFrame.colorId;
    },

    get stackTrace() {
      var stack = [];
      var cur = this.leafStackFrame;
      while (cur) {
        stack.push(cur);
        cur = cur.parentFrame;
      }
      stack.reverse();
      return stack;
    },

    getUserFriendlyStackTrace: function() {
      return this.stackTrace.map(function(x) {
        return x.category + ': ' + x.title;
      });
    },

    toJSON: function() {
      return {};
    }
  };

  return {
    Sample: Sample
  };
});
