// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TraceModel is a parsed representation of the
 * TraceEvents obtained from base/trace_event in which the begin-end
 * tokens are converted into a hierarchy of processes, threads,
 * subrows, and slices.
 *
 * The building block of the model is a slice. A slice is roughly
 * equivalent to function call executing on a specific thread. As a
 * result, slices may have one or more subslices.
 *
 * A thread contains one or more subrows of slices. Row 0 corresponds to
 * the "root" slices, e.g. the topmost slices. Row 1 contains slices that
 * are nested 1 deep in the stack, and so on. We use these subrows to draw
 * nesting tasks.
 *
 */
base.require('base.range');
base.require('base.events');
base.require('tracing.trace_model.process');
base.require('tracing.trace_model.kernel');
base.require('tracing.filter');

base.exportTo('tracing', function() {

  var Process = tracing.trace_model.Process;
  var Kernel = tracing.trace_model.Kernel;

  /**
   * Builds a model from an array of TraceEvent objects.
   * @param {Object=} opt_eventData Data from a single trace to be imported into
   *     the new model. See TraceModel.importTraces for details on how to
   *     import multiple traces at once.
   * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
   * Defaults to true.
   * @constructor
   */
  function TraceModel(opt_eventData, opt_shiftWorldToZero) {
    this.kernel = new Kernel(this);
    this.processes = {};
    this.importErrors = [];
    this.metadata = [];
    this.categories = [];
    this.bounds = new base.Range();
    this.instantEvents = [];

    if (opt_eventData)
      this.importTraces([opt_eventData], opt_shiftWorldToZero);
  }

  TraceModel.importerConstructors_ = [];

  /**
   * Registers an importer. All registered importers are considered
   * when processing an import request.
   *
   * @param {Function} importerConstructor The importer's constructor function.
   */
  TraceModel.registerImporter = function(importerConstructor) {
    TraceModel.importerConstructors_.push(importerConstructor);
  };

  TraceModel.prototype = {
    __proto__: base.EventTarget.prototype,

    get numProcesses() {
      var n = 0;
      for (var p in this.processes)
        n++;
      return n;
    },

    /**
     * @return {Process} Gets a TimlineProcess for a specified pid or
     * creates one if it does not exist.
     */
    getOrCreateProcess: function(pid) {
      if (!this.processes[pid])
        this.processes[pid] = new Process(this, pid);
      return this.processes[pid];
    },

    pushInstantEvent: function(instantEvent) {
      this.instantEvents.push(instantEvent);
    },

    /**
     * Generates the set of categories from the slices and counters.
     */
    updateCategories_: function() {
      var categoriesDict = {};
      this.kernel.addCategoriesToDict(categoriesDict);
      for (var pid in this.processes)
        this.processes[pid].addCategoriesToDict(categoriesDict);

      this.categories = [];
      for (var category in categoriesDict)
        if (category != '')
          this.categories.push(category);
    },

    updateBounds: function() {
      this.bounds.reset();

      this.kernel.updateBounds();
      this.bounds.addRange(this.kernel.bounds);

      for (var pid in this.processes) {
        this.processes[pid].updateBounds();
        this.bounds.addRange(this.processes[pid].bounds);
      }
    },

    shiftWorldToZero: function() {
      if (this.bounds.isEmpty)
        return;
      var timeBase = this.bounds.min;
      this.kernel.shiftTimestampsForward(-timeBase);
      for (var id in this.instantEvents)
        this.instantEvents[id].start -= timeBase;
      for (var pid in this.processes)
        this.processes[pid].shiftTimestampsForward(-timeBase);
      this.updateBounds();
    },

    getAllThreads: function() {
      var threads = [];
      for (var tid in this.kernel.threads) {
        threads.push(process.threads[tid]);
      }
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.threads) {
          threads.push(process.threads[tid]);
        }
      }
      return threads;
    },

    /**
     * @return {Array} An array of all processes in the model.
     */
    getAllProcesses: function() {
      var processes = [];
      for (var pid in this.processes)
        processes.push(this.processes[pid]);
      return processes;
    },

    /**
     * @return {Array} An array of all the counters in the model.
     */
    getAllCounters: function() {
      var counters = [];
      counters.push.apply(
          counters, base.dictionaryValues(this.kernel.counters));
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.counters) {
          counters.push(process.counters[tid]);
        }
      }
      return counters;
    },

    /**
     * @param {String} The name of the thread to find.
     * @return {Array} An array of all the matched threads.
     */
    findAllThreadsNamed: function(name) {
      var namedThreads = [];
      namedThreads.push.apply(
          namedThreads,
          this.kernel.findAllThreadsNamed(name));
      for (var pid in this.processes) {
        namedThreads.push.apply(
            namedThreads,
            this.processes[pid].findAllThreadsNamed(name));
      }
      return namedThreads;
    },

    createImporter_: function(eventData) {
      var importerConstructor;
      for (var i = 0; i < TraceModel.importerConstructors_.length; ++i) {
        if (TraceModel.importerConstructors_[i].canImport(eventData)) {
          importerConstructor = TraceModel.importerConstructors_[i];
          break;
        }
      }
      if (!importerConstructor)
        throw new Error(
            'Could not find an importer for the provided eventData.');

      var importer = new importerConstructor(
          this, eventData);
      return importer;
    },

    /**
     * Imports the provided traces into the model. The eventData type
     * is undefined and will be passed to all the  importers registered
     * via TraceModel.registerImporter. The first importer that returns true
     * for canImport(events) will be used to import the events.
     *
     * The primary trace is provided via the eventData variable. If multiple
     * traces are to be imported, specify the first one as events, and the
     * remainder in the opt_additionalEventData array.
     *
     * @param {Array} traces An array of eventData to be imported. Each
     * eventData should correspond to a single trace file and will be handled by
     * a separate importer.
     * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
     * Defaults to true.
     * @param {bool=} opt_pruneEmptyContainers Whether to prune empty
     * containers. Defaults to true.
     */
    importTraces: function(traces,
                           opt_shiftWorldToZero,
                           opt_pruneEmptyContainers) {
      if (opt_shiftWorldToZero === undefined)
        opt_shiftWorldToZero = true;
      if (opt_pruneEmptyContainers === undefined)
        opt_pruneEmptyContainers = true;

      // Copy the traces array, we may mutate it.
      traces = traces.slice(0);

      // Figure out which importers to use.
      var importers = [];
      for (var i = 0; i < traces.length; ++i)
        importers.push(this.createImporter_(traces[i]));

      // Some traces have other traces inside them. Before doing the full
      // import, ask the importer if it has any subtraces, and if so, create an
      // importer for that, also.
      for (var i = 0; i < importers.length; i++) {
        var subTrace = importers[i].extractSubtrace();
        if (!subTrace)
          continue;
        traces.push(subTrace);
        importers.push(this.createImporter_(subTrace));
      }

      // Sort them on priority. This ensures importing happens in a predictable
      // order, e.g. linux_perf_importer before trace_event_importer.
      importers.sort(function(x, y) {
        return x.importPriority - y.importPriority;
      });

      // Run the import.
      for (var i = 0; i < importers.length; i++)
        importers[i].importEvents(i > 0);

      // Autoclose open slices.
      this.updateBounds();
      this.kernel.autoCloseOpenSlices(this.bounds.max);
      for (var pid in this.processes)
        this.processes[pid].autoCloseOpenSlices(this.bounds.max);

      // Finalize import.
      for (var i = 0; i < importers.length; i++)
        importers[i].finalizeImport();

      // Run preinit.
      for (var pid in this.processes)
        this.processes[pid].preInitializeObjects();

      // Prune empty containers.
      if (opt_pruneEmptyContainers) {
        this.kernel.pruneEmptyContainers();
        for (var pid in this.processes) {
          this.processes[pid].pruneEmptyContainers();
        }
      }

      // Merge kernel and userland slices on each thread.
      for (var pid in this.processes) {
        this.processes[pid].mergeKernelWithUserland();
      }

      this.updateBounds();

      this.updateCategories_();

      if (opt_shiftWorldToZero)
        this.shiftWorldToZero();

      // Join refs.
      for (var i = 0; i < importers.length; i++)
        importers[i].joinRefs();

      // Delete any undeleted objects.
      for (var pid in this.processes)
        this.processes[pid].autoDeleteObjects(this.bounds.max);

      // Run initializers.
      for (var pid in this.processes)
        this.processes[pid].initializeObjects();
    }
  };

  /**
   * Importer for empty strings and arrays.
   * @constructor
   */
  function TraceModelEmptyImporter(events) {
    this.importPriority = 0;
  };

  TraceModelEmptyImporter.canImport = function(eventData) {
    if (eventData instanceof Array && eventData.length == 0)
      return true;
    if (typeof(eventData) === 'string' || eventData instanceof String) {
      return eventData.length == 0;
    }
    return false;
  };

  TraceModelEmptyImporter.prototype = {
    __proto__: Object.prototype,

    extractSubtrace: function() {
      return undefined;
    },
    importEvents: function() {
    },
    finalizeImport: function() {
    },
    joinRefs: function() {
    }
  };

  TraceModel.registerImporter(TraceModelEmptyImporter);

  return {
    TraceModel: TraceModel
  };
});
