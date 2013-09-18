// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.util');

base.exportTo('system_stats', function() {
  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  /**
   * @constructor
   */
  function SystemStatsSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  /**
   * @constructor
   */
  function SystemStatsSnapshot(objectInstance, ts, args) {
    this.objectInstance = objectInstance;
    this.ts = ts;
    this.args = args;
    this.stats = args;
  }

  SystemStatsSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    initialize: function() {
      if (this.args.length == 0)
        throw new Error('No system stats snapshot data.');
      this.stats_ = this.args;
    },

    getStats: function() {
      return this.stats_;
    },

    setStats: function(stats) {
      this.stats_ = stats;
    }
  };

  ObjectSnapshot.register('base::TraceEventSystemStatsMonitor::SystemStats',
                          SystemStatsSnapshot);

  return {
    SystemStatsSnapshot: SystemStatsSnapshot
  };
});
