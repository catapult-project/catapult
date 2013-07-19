// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.trace_model_event');

/**
 * @fileoverview Provides the InstantEvent class.
 */
base.exportTo('tracing.trace_model', function() {
  var InstantEventType = {
    GLOBAL: 1,
    PROCESS: 2,
    THREAD: 3
  };

  function InstantEvent(category, title, colorId, start, args) {
    tracing.trace_model.TraceModelEvent.apply(this, arguments);

    this.type = undefined;
  };

  InstantEvent.prototype = {
    __proto__: tracing.trace_model.TraceModelEvent.prototype
  };

  function GlobalInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantEventType.GLOBAL;
  };

  GlobalInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  function ProcessInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantEventType.PROCESS;
  };

  ProcessInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  function ThreadInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantEventType.THREAD;
  };

  ThreadInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  return {
    GlobalInstantEvent: GlobalInstantEvent,
    ProcessInstantEvent: ProcessInstantEvent,
    ThreadInstantEvent: ThreadInstantEvent,

    InstantEventType: InstantEventType
  };
});
