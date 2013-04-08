// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Model is a parsed representation of the
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
base.require('range');
base.require('event_target');
base.require('model.process');
base.require('model.kernel');
base.require('model.cpu');
base.require('filter');

base.exportTo('tracing', function() {

  var Process = tracing.model.Process;
  var Kernel = tracing.model.Kernel;
  var Cpu = tracing.model.Cpu;

  /**
   * Builds a model from an array of TraceEvent objects.
   * @param {Object=} opt_eventData Data from a single trace to be imported into
   *     the new model. See Model.importTraces for details on how to
   *     import multiple traces at once.
   * @param {bool=} opt_shiftWorldToZero Whether to shift the world to zero.
   * Defaults to true.
   * @constructor
   */
  function Model(opt_eventData, opt_shiftWorldToZero) {
    this.kernel = new Kernel();
    this.cpus = {};
    this.processes = {};
    this.importErrors = [];
    this.metadata = [];
    this.categories = [];
    this.bounds = new base.Range();

    if (opt_eventData)
      this.importTraces([opt_eventData], opt_shiftWorldToZero);
  }

  var importerConstructors = [];

  /**
   * Registers an importer. All registered importers are considered
   * when processing an import request.
   *
   * @param {Function} importerConstructor The importer's constructor function.
   */
  Model.registerImporter = function(importerConstructor) {
    importerConstructors.push(importerConstructor);
  };

  Model.prototype = {
    __proto__: base.EventTarget.prototype,

    get numProcesses() {
      var n = 0;
      for (var p in this.processes)
        n++;
      return n;
    },

    /**
     * @return {Cpu} Gets a specific Cpu or creates one if
     * it does not exist.
     */
    getOrCreateCpu: function(cpuNumber) {
      if (!this.cpus[cpuNumber])
        this.cpus[cpuNumber] = new Cpu(cpuNumber);
      return this.cpus[cpuNumber];
    },

    /**
     * @return {Process} Gets a TimlineProcess for a specified pid or
     * creates one if it does not exist.
     */
    getOrCreateProcess: function(pid) {
      if (!this.processes[pid])
        this.processes[pid] = new Process(pid);
      return this.processes[pid];
    },

    /**
     * Generates the set of categories from the slices and counters.
     */
    updateCategories_: function() {
      var categoriesDict = {};
      this.kernel.addCategoriesToDict(categoriesDict);
      for (var pid in this.processes)
        this.processes[pid].addCategoriesToDict(categoriesDict);
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].addCategoriesToDict(categoriesDict);

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

      for (var cpuNumber in this.cpus) {
        this.cpus[cpuNumber].updateBounds();
        this.bounds.addRange(this.cpus[cpuNumber].bounds);
      }
    },

    shiftWorldToZero: function() {
      if (this.bounds.isEmpty)
        return;
      var timeBase = this.bounds.min;
      this.kernel.shiftTimestampsForward(-timeBase);
      for (var pid in this.processes)
        this.processes[pid].shiftTimestampsForward(-timeBase);
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].shiftTimestampsForward(-timeBase);
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
     * @return {Array} An array of all cpus in the model.
     */
    getAllCpus: function() {
      var cpus = [];
      for (var cpu in this.cpus)
        cpus.push(this.cpus[cpu]);
      return cpus;
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
      for (var pid in this.processes) {
        var process = this.processes[pid];
        for (var tid in process.counters) {
          counters.push(process.counters[tid]);
        }
      }
      for (var cpuNumber in this.cpus) {
        var cpu = this.cpus[cpuNumber];
        for (var counterName in cpu.counters)
          counters.push(cpu.counters[counterName]);
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
      for (var i = 0; i < importerConstructors.length; ++i) {
        if (importerConstructors[i].canImport(eventData)) {
          importerConstructor = importerConstructors[i];
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
     * via Model.registerImporter. The first importer that returns true
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
     */
    importTraces: function(traces,
                           opt_shiftWorldToZero) {
      if (opt_shiftWorldToZero === undefined)
        opt_shiftWorldToZero = true;

      // Figure out which importers to use.
      var importers = [];
      for (var i = 0; i < traces.length; ++i)
        importers.push(this.createImporter_(traces[i]));

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
      for (var pid in this.processes) {
        this.processes[pid].autoCloseOpenSlices(this.bounds.max);
      }

      // Finalize import.
      for (var i = 0; i < importers.length; i++)
        importers[i].finalizeImport();

      // Prune empty containers.
      this.kernel.pruneEmptyContainers();
      for (var pid in this.processes) {
        this.processes[pid].pruneEmptyContainers();
      }

      // Merge kernel and userland slices on each thread.
      for (var pid in this.processes) {
        this.processes[pid].mergeKernelWithUserland();
      }

      this.updateBounds();

      this.updateCategories_();

      if (opt_shiftWorldToZero)
        this.shiftWorldToZero();
    }
  };

  /**
   * Importer for empty strings and arrays.
   * @constructor
   */
  function ModelEmptyImporter(events) {
    this.importPriority = 0;
  };

  ModelEmptyImporter.canImport = function(eventData) {
    if (eventData instanceof Array && eventData.length == 0)
      return true;
    if (typeof(eventData) === 'string' || eventData instanceof String) {
      return eventData.length == 0;
    }
    return false;
  };

  ModelEmptyImporter.prototype = {
    __proto__: Object.prototype,

    importEvents: function() {
    },
    finalizeImport: function() {
    }
  };

  Model.registerImporter(ModelEmptyImporter);

  return {
    Model: Model
  };
});
