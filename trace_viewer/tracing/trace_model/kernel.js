// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Process class.
 */
tvcm.require('tracing.trace_model.cpu');
tvcm.require('tracing.trace_model.process_base');

tvcm.exportTo('tracing.trace_model', function() {

  var Cpu = tracing.trace_model.Cpu;
  var ProcessBase = tracing.trace_model.ProcessBase;

  /**
   * The Kernel represents kernel-level objects in the
   * model.
   * @constructor
   */
  function Kernel(model) {
    if (model === undefined)
      throw new Error('model must be provided');
    ProcessBase.call(this, model);
    this.cpus = {};
  };

  /**
   * Comparison between kernels is pretty meaningless.
   */
  Kernel.compare = function(x, y) {
    return 0;
  };

  Kernel.prototype = {
    __proto__: ProcessBase.prototype,

    compareTo: function(that) {
      return Kernel.compare(this, that);
    },

    get userFriendlyName() {
      return 'Kernel';
    },

    get userFriendlyDetails() {
      return 'Kernel';
    },

    /**
     * @return {Cpu} Gets a specific Cpu or creates one if
     * it does not exist.
     */
    getOrCreateCpu: function(cpuNumber) {
      if (!this.cpus[cpuNumber])
        this.cpus[cpuNumber] = new Cpu(this, cpuNumber);
      return this.cpus[cpuNumber];
    },

    shiftTimestampsForward: function(amount) {
      ProcessBase.prototype.shiftTimestampsForward.call(this);
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].shiftTimestampsForward(amount);
    },

    updateBounds: function() {
      ProcessBase.prototype.updateBounds.call(this);
      for (var cpuNumber in this.cpus) {
        var cpu = this.cpus[cpuNumber];
        cpu.updateBounds();
        this.bounds.addRange(cpu.bounds);
      }
    },

    createSubSlices: function() {
      ProcessBase.prototype.createSubSlices.call(this);
      for (var cpuNumber in this.cpus) {
        var cpu = this.cpus[cpuNumber];
        cpu.createSubSlices();
      }
    },

    addCategoriesToDict: function(categoriesDict) {
      ProcessBase.prototype.addCategoriesToDict.call(this, categoriesDict);
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].addCategoriesToDict(categoriesDict);
    },

    getSettingsKey: function() {
      return 'kernel';
    },

    iterateAllEvents: function(callback, opt_this) {
      for (var cpuNumber in this.cpus)
        this.cpus[cpuNumber].iterateAllEvents(callback, opt_this);

      ProcessBase.prototype.iterateAllEvents.call(this, callback, opt_this);
    }
  };

  return {
    Kernel: Kernel
  };
});
