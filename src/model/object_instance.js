// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the ObjectSnapshot and ObjectHistory classes.
 */
base.require('range');
base.require('sorted_array_utils');

base.exportTo('tracing.model', function() {

  /**
   * A snapshot of an object instance, at a given moment in time.
   *
   * @constructor
   */
  function ObjectInstanceSnapshot(objectInstance, ts, args) {
    this.objectInstance = objectInstance;
    this.ts = ts;
    this.args = args;
    this.validBeforeTs = Number.MAX_VALUE;
  }

  ObjectInstanceSnapshot.prototype = {
    __proto__: Object.prototype,
  };

  /**
   * An object with a specific id, whose state has been snapshotted several
   * times.
   *
   * @constructor
   */
  function ObjectInstance(parent, id, category, name, creationTs) {
    this.parent = parent;
    this.id = id;
    this.category = category;
    this.name = name;
    this.creationTs = creationTs;
    this.deletionTs = Number.MAX_VALUE;
    this.bounds = new base.Range();
    this.snapshots = [];
  }

  ObjectInstance.prototype = {
    __proto__: Object.prototype,

    addSnapshot: function(ts, args) {
      if (ts < this.creationTs)
        throw new Error('Snapshots must be >= instance.creationTs');
      if (this.deletionTs != Number.MAX_VALUE)
        throw new Error('The instance has been deleted. ' +
                        'No more snapshots can be added.');

      var lastSnapshot;
      if (this.snapshots.length > 0) {
        lastSnapshot = this.snapshots[this.snapshots.length - 1];
        if (lastSnapshot.ts == ts)
          throw new Error('Snapshots already exists at this time!');
        if (ts < lastSnapshot.ts) {
          throw new Error(
            'Snapshots must be added in increasing timestamp order');
        }
      }

      var snapshot = new ObjectInstanceSnapshot(this, ts, args);
      if (lastSnapshot)
        lastSnapshot.validBeforeTs = ts;
      this.snapshots.push(snapshot);
      return snapshot;
    },

    wasDeleted: function(ts) {
      var lastSnapshot;
      if (this.snapshots.length > 0) {
        lastSnapshot = this.snapshots[this.snapshots.length - 1];
        if (lastSnapshot.ts > ts)
          throw new Error(
            'Instance cannot be deleted at ts=' +
              ts + '. A snapshot exists that is older.');
      }
      this.deletionTs = ts;
      if (lastSnapshot)
        lastSnapshot.validBeforeTs = this.deletionTs;
    },

    getSnapshotAt: function(ts) {
      if (ts < this.creationTs || ts > this.deletionTs)
        throw new Error('ts must be within lifetime of this instance');

      var i = tracing.findLowIndexInSortedIntervals(
        this.snapshots,
        function(snapshot) { return snapshot.ts; },
        function(snapshot) { return snapshot.validBeforeTs - snapshot.ts; },
        ts);
      if (i < 0 || i >= this.snapshots.length)
        return undefined;
      return this.snapshots[i];
    },

    updateBounds: function() {
      this.bounds.reset();
      this.bounds.addValue(this.creationTs);
      if (this.deletionTs != Number.MAX_VALUE)
        this.bounds.addValue(this.deletionTs);
      else if (this.snapshots.length > 0)
        this.bounds.addValue(this.snapshots[this.snapshots.length - 1].ts);
    },

    shiftTimestampsForward: function(amount) {
      this.creationTs += amount;
      if (this.deletionTs != Number.MAX_VALUE)
        this.deletionTs += amount;
      this.snapshots.forEach(function(snapshot) {
        snapshot.ts += amount;
      });
    }
  };

  return {
    ObjectInstanceSnapshot: ObjectInstanceSnapshot,
    ObjectInstance: ObjectInstance,
  };
});
