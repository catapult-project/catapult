// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Instant class.
 *
 * Note, this has the save API as the slice class.
 */
base.exportTo('tracing.trace_model', function() {
  var InstantType = {
    GLOBAL: 1,
    PROCESS: 2,
    THREAD: 3
  };

  function InstantEvent(category, title, colorId, start, args) {
    this.category = category || '';
    this.title = title;
    this.colorId = colorId;
    this.start = start;
    this.args = args;
    this.type = undefined;
  };

  InstantEvent.prototype = {
    __proto__: Object,

    selected: false,

    duration: 0,

    get end() {
      return this.start;
    }
  };

  function GlobalInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantType.GLOBAL;
  };

  GlobalInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  function ProcessInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantType.PROCESS;
  };

  ProcessInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  function ThreadInstantEvent(category, title, colorId, start, args) {
    InstantEvent.apply(this, arguments);
    this.type = InstantType.THREAD;
  };

  ThreadInstantEvent.prototype = {
    __proto__: InstantEvent.prototype
  };

  return {
    GlobalInstantEvent: GlobalInstantEvent,
    ProcessInstantEvent: ProcessInstantEvent,
    ThreadInstantEvent: ThreadInstantEvent,

    InstantType: InstantType
  };
});
