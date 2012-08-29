// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimelineProcess class.
 */
base.require('timeline_thread');
base.require('timeline_counter');
base.exportTo('tracing', function() {

  var TimelineThread = tracing.TimelineThread;
  var TimelineCounter = tracing.TimelineCounter;

  /**
   * The TimelineProcess represents a single process in the
   * trace. Right now, we keep this around purely for bookkeeping
   * reasons.
   * @constructor
   */
  function TimelineProcess(pid) {
    this.pid = pid;
    this.threads = {};
    this.counters = {};
  };

  TimelineProcess.prototype = {
    get numThreads() {
      var n = 0;
      for (var p in this.threads) {
        n++;
      }
      return n;
    },

    /**
     * Shifts all the timestamps inside this process forward by the amount
     * specified.
     */
    shiftTimestampsForward: function(amount) {
      for (var tid in this.threads)
        this.threads[tid].shiftTimestampsForward(amount);
      for (var id in this.counters)
        this.counters[id].shiftTimestampsForward(amount);
    },

    /**
     * @return {TimlineThread} The thread identified by tid on this process,
     * creating it if it doesn't exist.
     */
    getOrCreateThread: function(tid) {
      if (!this.threads[tid])
        this.threads[tid] = new TimelineThread(this, tid);
      return this.threads[tid];
    },

    /**
     * @return {TimlineCounter} The counter on this process named 'name',
     * creating it if it doesn't exist.
     */
    getOrCreateCounter: function(cat, name) {
      var id = cat + '.' + name;
      if (!this.counters[id])
        this.counters[id] = new TimelineCounter(this, id, cat, name);
      return this.counters[id];
    }
  };

  /**
   * Comparison between processes that orders by pid.
   */
  TimelineProcess.compare = function(x, y) {
    return x.pid - y.pid;
  };

  return {
    TimelineProcess: TimelineProcess
  };
});
