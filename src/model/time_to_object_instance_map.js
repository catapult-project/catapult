// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the TimeToObjectInstanceMap class.
 */
base.require('range');
base.require('sorted_array_utils');

base.exportTo('tracing.model', function() {

  /**
   * Tracks all the instances associated with a given ID over its lifetime.
   *
   * An id can be used multiple times throughout a trace, referring to different
   * objects at different times. This data structure does the bookkeeping to
   * figure out what ObjectInstance is referred to at a given timestamp.
   *
   * @constructor
   */
  function TimeToObjectInstanceMap(createInstanceCallback) {
    this.instances = [];
    this.createInstanceCallback = createInstanceCallback;
  }

  TimeToObjectInstanceMap.prototype = {
    idWasCreated: function(ts) {
      if (this.instances.length == 0) {
        this.instances.push(this.createInstanceCallback(ts));
        return this.instances[0];
      }

      var lastInstance = this.instances[this.instances.length - 1];
      if (ts < lastInstance.deletionTs) {
        throw new Error('Mutation of the TimeToObjectInstanceMap must be ' +
                        'done in ascending timestamp order.');
      }
      lastInstance = this.createInstanceCallback(ts);
      this.instances.push(lastInstance);
      return lastInstance;
    },

    addSnapshot: function(ts, args) {
      if (this.instances.length == 0)
        this.instances.push(this.createInstanceCallback(ts));

      var lastInstance = this.instances[this.instances.length - 1];
      if (ts < lastInstance.creationTs) {
        throw new Error('Mutation of the TimeToObjectInstanceMap must be ' +
                        'done in ascending timestamp order.');
      }
      if (ts >= lastInstance.deletionTs) {
        lastInstance = this.createInstanceCallback(ts);
        this.instances.push(lastInstance);
      }
      return lastInstance.addSnapshot(ts, args);
    },

    idWasDeleted: function(ts) {
      if (this.instances.length == 0)
        this.instances.push(this.createInstanceCallback(ts));
      var lastInstance = this.instances[this.instances.length - 1];
      if (ts < lastInstance.creationTs)
        throw new Error('Cannot delete a id before it was crated');
      if (lastInstance.deletionTs == Number.MAX_VALUE) {
        lastInstance.wasDeleted(ts);
        return lastInstance;
      }

      if (lastInstance.deletionTs != Number.MAX_VALUE &&
          ts < lastInstance.deletionTs)
        throw new Error('id was already deleted earlier.');

      // The item was deleted a few times, with no snapshots in-between.
      // No action is needed.
      return undefined;
    },

    getInstanceAt: function(ts) {
      var i = tracing.findLowIndexInSortedIntervals(
        this.instances,
        function(inst) { return inst.creationTs; },
        function(inst) { return inst.deletionTs - inst.creationTs; },
        ts);
      if (i < 0 || i >= this.instances.length)
        return undefined;
      return this.instances[i];
    }
  };

  return {
    TimeToObjectInstanceMap: TimeToObjectInstanceMap
  };
});
