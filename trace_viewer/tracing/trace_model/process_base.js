// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the ProcessBase class.
 */
tvcm.require('tvcm.guid');
tvcm.require('tvcm.range');
tvcm.require('tracing.trace_model.counter');
tvcm.require('tracing.trace_model.object_collection');
tvcm.require('tracing.trace_model.thread');
tvcm.require('tracing.trace_model_settings');
tvcm.exportTo('tracing.trace_model', function() {

  var Thread = tracing.trace_model.Thread;
  var Counter = tracing.trace_model.Counter;

  /**
   * The ProcessBase is a partial base class, upon which Kernel
   * and Process are built.
   *
   * @constructor
   */
  function ProcessBase(model) {
    if (!model)
      throw new Error('Must provide a model');
    this.guid_ = tvcm.GUID.allocate();
    this.model = model;
    this.threads = {};
    this.counters = {};
    this.objects = new tracing.trace_model.ObjectCollection(this);
    this.bounds = new tvcm.Range();
    this.sortIndex = 0;
    this.ephemeralSettings = {};
  };

  ProcessBase.compare = function(x, y) {
    return x.sortIndex - y.sortIndex;
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

    toJSON: function() {
      var obj = new Object();
      var keys = Object.keys(this);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (typeof this[key] == 'function')
          continue;
        if (key == 'model')
          continue;
        obj[key] = this[key];
      }
      return obj;
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
      this.objects.shiftTimestampsForward(amount);
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

    autoDeleteObjects: function(maxTimestamp) {
      this.objects.autoDeleteObjects(maxTimestamp);
    },

    /**
     * Called by the model after finalizing imports,
     * but before joining refs.
     */
    preInitializeObjects: function() {
      this.objects.preInitializeAllObjects();
    },

    /**
     * Called by the model after joining refs.
     */
    initializeObjects: function() {
      this.objects.initializeAllObjects();
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
      this.objects.updateBounds();
      this.bounds.addRange(this.objects.bounds);
    },

    addCategoriesToDict: function(categoriesDict) {
      for (var tid in this.threads)
        this.threads[tid].addCategoriesToDict(categoriesDict);
      for (var id in this.counters)
        categoriesDict[this.counters[id].category] = true;
      this.objects.addCategoriesToDict(categoriesDict);
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
     * @return {TimelineThread} The thread identified by tid on this process,
     * creating it if it doesn't exist.
     */
    getOrCreateThread: function(tid) {
      if (!this.threads[tid])
        this.threads[tid] = new Thread(this, tid);
      return this.threads[tid];
    },

    /**
     * @return {TimelineCounter} The counter on this process named 'name',
     * creating it if it doesn't exist.
     */
    getOrCreateCounter: function(cat, name) {
      var id = cat + '.' + name;
      if (!this.counters[id])
        this.counters[id] = new Counter(this, id, cat, name);
      return this.counters[id];
    },

    getSettingsKey: function() {
      throw new Error('Not implemented');
    },

    iterateAllEvents: function(callback, opt_this) {
      for (var tid in this.threads)
        this.threads[tid].iterateAllEvents(callback, opt_this);

      for (var id in this.counters)
        this.counters[id].iterateAllEvents(callback, opt_this);

      this.objects.iterateAllEvents(callback, opt_this);
    }
  };

  return {
    ProcessBase: ProcessBase
  };
});
