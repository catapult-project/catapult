// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Process class.
 */
base.require('model.process_base');
base.exportTo('tracing.model', function() {

  /**
   * The Process represents a single userland process in the
   * trace.
   * @constructor
   */
  function Process(pid) {
    tracing.model.ProcessBase.call(this);
    this.pid = pid;
  };

  /**
   * Comparison between processes that orders by pid.
   */
  Process.compare = function(x, y) {
    return x.pid - y.pid;
  };

  Process.prototype = {
    __proto__: tracing.model.ProcessBase.prototype,

    compareTo: function(that) {
      return Process.compare(this, that);
    },

    get userFriendlyName() {
      return this.pid;
    },

    get userFriendlyDetails() {
      return 'pid: ' + this.pid;
    },
  };

  return {
    Process: Process
  };
});
