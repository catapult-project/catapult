// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the ObjectSnapshot and ObjectHistory classes.
 */
base.require('base.range');
base.require('base.sorted_array_utils');

base.exportTo('tracing.model', function() {

  /**
   * A snapshot of an object instance, at a given moment in time.
   *
   * Initialization of snapshots and instances is three phased:
   *
   * 1. Instances and snapshots are constructed. This happens during event
   *    importing. Little should be done here, because the object's data
   *    are still being used by the importer to reconstruct object references.
   *
   * 2. Instances and snapshtos are preinitialized. This happens after implicit
   *    objects have been found, but before any references have been found and
   *    switched to direct references. Thus, every snapshot stands on its own.
   *    This is a good time to do global field renaming and type conversion,
   *    e.g. recognizing domain-specific types and converting from C++ naming
   *    convention to JS.
   *
   * 3. Instances and snapshtos are initialized. At this point, {id_ref:
   *    '0x1000'} fields have been converted to snapshot references. This is a
   *    good time to generic initialization steps and argument verification.
   *
   * @constructor
   */
  function ObjectSnapshot(objectInstance, ts, args) {
    this.objectInstance = objectInstance;
    this.ts = ts;
    this.args = args;
    this.selected = false;
  }

  ObjectSnapshot.prototype = {
    __proto__: Object.prototype,

    /**
     * See ObjectSnapshot constructor notes on object initialization.
     */
    preInitialize: function() {
    },

    /**
     * See ObjectSnapshot constructor notes on object initialization.
     */
    initialize: function() {
    }
  };

  ObjectSnapshot.nameToConstructorMap_ = {};
  ObjectSnapshot.register = function(name, constructor) {
    if (ObjectSnapshot.nameToConstructorMap_[name])
      throw new Error('Constructor already registerd for ' + name);
    ObjectSnapshot.nameToConstructorMap_[name] = constructor;
  };

  ObjectSnapshot.unregister = function(name) {
    delete ObjectSnapshot.nameToConstructorMap_[name];
  };

  ObjectSnapshot.getConstructor = function(name) {
    if (ObjectSnapshot.nameToConstructorMap_[name])
      return ObjectSnapshot.nameToConstructorMap_[name];
    return ObjectSnapshot;
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
    this.creationTsWasExplicit = false;
    this.deletionTs = Number.MAX_VALUE;
    this.selected = false;
    this.colorId = 0;
    this.bounds = new base.Range();
    this.snapshots = [];
    this.hasImplicitSnapshots = false;
  }

  ObjectInstance.prototype = {
    __proto__: Object.prototype,

    get typeName() {
      return this.name;
    },

    addSnapshot: function(ts, args) {
      if (ts < this.creationTs)
        throw new Error('Snapshots must be >= instance.creationTs');
      if (ts >= this.deletionTs)
        throw new Error('Snapshots cannot be added after ' +
                        'an objects deletion timestamp.');

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

      var snapshotConstructor = tracing.model.ObjectSnapshot.getConstructor(
          this.name);
      var snapshot = new snapshotConstructor(this, ts, args);
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
    },

    /**
     * See ObjectSnapshot constructor notes on object initialization.
     */
    preInitialize: function() {
      for (var i = 0; i < this.snapshots.length; i++)
        this.snapshots[i].preInitialize();
    },

    /**
     * See ObjectSnapshot constructor notes on object initialization.
     */
    initialize: function() {
      for (var i = 0; i < this.snapshots.length; i++)
        this.snapshots[i].initialize();
    },

    getSnapshotAt: function(ts) {
      if (ts < this.creationTs) {
        if (this.creationTsWasExplicit)
          throw new Error('ts must be within lifetime of this instance');
        return this.snapshots[0];
      }
      if (ts > this.deletionTs)
        throw new Error('ts must be within lifetime of this instance');

      var snapshots = this.snapshots;
      var i = base.findLowIndexInSortedIntervals(
          snapshots,
          function(snapshot) { return snapshot.ts; },
          function(snapshot, i) {
            if (i == snapshots.length - 1)
              return snapshots[i].objectInstance.deletionTs;
            return snapshots[i + 1].ts - snapshots[i].ts;
          },
          ts);
      if (i < 0) {
        // Note, this is a little bit sketchy: this lets early ts point at the
        // first snapshot, even before it is taken. We do this because raster
        // tasks usually post before their tile snapshots are dumped. This may
        // be a good line of code to re-visit if we start seeing strange and
        // confusing object references showing up in the traces.
        return this.snapshots[0];
      }
      if (i >= this.snapshots.length)
        return this.snapshots[this.snapshots.length - 1];
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

  ObjectInstance.nameToConstructorMap_ = {};
  ObjectInstance.register = function(name, constructor) {
    if (ObjectInstance.nameToConstructorMap_[name])
      throw new Error('Constructor already registerd for ' + name);
    ObjectInstance.nameToConstructorMap_[name] = constructor;
  };

  ObjectInstance.unregister = function(name) {
    delete ObjectInstance.nameToConstructorMap_[name];
  };

  ObjectInstance.getConstructor = function(name) {
    if (ObjectInstance.nameToConstructorMap_[name])
      return ObjectInstance.nameToConstructorMap_[name];
    return ObjectInstance;
  };

  return {
    ObjectSnapshot: ObjectSnapshot,
    ObjectInstance: ObjectInstance
  };
});
