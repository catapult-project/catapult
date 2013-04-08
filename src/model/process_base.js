// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the ProcessBase class.
 */
base.require('range');
base.require('guid');
base.require('model.thread');
base.require('model.counter');
base.exportTo('tracing.model', function() {

  var Thread = tracing.model.Thread;
  var Counter = tracing.model.Counter;

  /**
   * The ProcessBase is an partial base class, upon which Kernel
   * and Process are built.
   *
   * @constructor
   */
  function ProcessBase() {
    this.guid_ = tracing.GUID.allocate();
    this.threads = {};
    this.counters = {};
    this.bounds = new base.Range();
  };

  ProcessBase.prototype = {
    /*
     * @return {Number} A globally unique identifier for this counter.
     */
    get guid() {
      return this.guid_;
    },

    /**
     * Gets the number of threads in this process.
     */
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
     * Closes any open slices.
     */
    autoCloseOpenSlices: function(opt_maxTimestamp) {
      for (var tid in this.threads) {
        var thread = this.threads[tid];
        thread.autoCloseOpenSlices(opt_maxTimestamp);
      }
    },

    /**
     * Merge slices from the kernel with those from userland for each thread.
     */
    mergeKernelWithUserland: function() {
      for (var tid in this.threads) {
        var thread = this.threads[tid];
        thread.mergeKernelWithUserland();
      }
    },

    updateBounds: function() {
      this.bounds.reset();
      for (var tid in this.threads) {
        this.threads[tid].updateBounds();
        this.bounds.addRange(this.threads[tid].bounds);
      }
      for (var id in this.counters) {
        this.counters[id].updateBounds();
        this.bounds.addRange(this.counters[id].bounds);
      }
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var tid in this.threads)
        this.threads[tid].addCategoriesToDict(categoriesDict);
      for (var id in this.counters)
        categoriesDict[this.counters[id].category] = true;
    },

    /**
     * @param {String} The name of the thread to find.
     * @return {Array} An array of all the matched threads.
     */
    findAllThreadsNamed: function(name) {
      var namedThreads = [];
      for (var tid in this.threads) {
        var thread = this.threads[tid];
        if (thread.name == name)
          namedThreads.push(thread);
      }
      return namedThreads;
    },

    /**
     * Removes threads from the process that are fully empty.
     */
    pruneEmptyContainers: function() {
      var threadsToKeep = {};
      for (var tid in this.threads) {
        var thread = this.threads[tid];
        if (!thread.isEmpty)
          threadsToKeep[tid] = thread;
      }
      this.threads = threadsToKeep;
    },

    /**
     * @return {TimlineThread} The thread identified by tid on this process,
     * creating it if it doesn't exist.
     */
    getOrCreateThread: function(tid) {
      if (!this.threads[tid])
        this.threads[tid] = new Thread(this, tid);
      return this.threads[tid];
    },

    /**
     * @return {TimlineCounter} The counter on this process named 'name',
     * creating it if it doesn't exist.
     */
    getOrCreateCounter: function(cat, name) {
      var id = cat + '.' + name;
      if (!this.counters[id])
        this.counters[id] = new Counter(this, id, cat, name);
      return this.counters[id];
    }
  };

  return {
    ProcessBase: ProcessBase
  };
});
