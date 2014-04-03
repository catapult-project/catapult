// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the Process class.
 */
tvcm.require('tracing.trace_model.process_base');
tvcm.exportTo('tracing.trace_model', function() {

  var ProcessBase = tracing.trace_model.ProcessBase;

  /**
   * The Process represents a single userland process in the
   * trace.
   * @constructor
   */
  function Process(model, pid) {
    if (model === undefined)
      throw new Error('model must be provided');
    if (pid === undefined)
      throw new Error('pid must be provided');
    tracing.trace_model.ProcessBase.call(this, model);
    this.pid = pid;
    this.name = undefined;
    this.labels = [];
    this.instantEvents = [];
  };

  /**
   * Comparison between processes that orders by pid.
   */
  Process.compare = function(x, y) {
    var tmp = tracing.trace_model.ProcessBase.compare(x, y);
    if (tmp)
      return tmp;

    tmp = tvcm.comparePossiblyUndefinedValues(
        x.name, y.name,
        function(x, y) { return x.localeCompare(y); });
    if (tmp)
      return tmp;

    tmp = tvcm.compareArrays(x.labels, y.labels,
        function(x, y) { return x.localeCompare(y); });
    if (tmp)
      return tmp;

    return x.pid - y.pid;
  };

  Process.prototype = {
    __proto__: tracing.trace_model.ProcessBase.prototype,

    compareTo: function(that) {
      return Process.compare(this, that);
    },

    pushInstantEvent: function(instantEvent) {
      this.instantEvents.push(instantEvent);
    },

    addLabelIfNeeded: function(labelName) {
      for (var i = 0; i < this.labels.length; i++) {
        if (this.labels[i] === labelName)
          return;
      }
      this.labels.push(labelName);
    },

    get userFriendlyName() {
      var res;
      if (this.name)
        res = this.name + ' (pid ' + this.pid + ')';
      else
        res = 'Process ' + this.pid;
      if (this.labels.length)
        res += ': ' + this.labels.join(', ');
      return res;
    },

    get userFriendlyDetails() {
      if (this.name)
        return this.name + ' (pid ' + this.pid + ')';
      return 'pid: ' + this.pid;
    },

    getSettingsKey: function() {
      if (!this.name)
        return undefined;
      if (!this.labels.length)
        return 'processes.' + this.name;
      return 'processes.' + this.name + '.' + this.labels.join('.');
    },

    shiftTimestampsForward: function(amount) {
      for (var id in this.instantEvents)
        this.instantEvents[id].start += amount;

      tracing.trace_model.ProcessBase.prototype
          .shiftTimestampsForward.apply(this, arguments);
    },

    iterateAllEvents: function(callback, opt_this) {
      this.instantEvents.forEach(callback, opt_this);

      ProcessBase.prototype.iterateAllEvents.call(this, callback, opt_this);
    }
  };

  return {
    Process: Process
  };
});
