// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('tracing.trace_model', function() {
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

  return {
    ObjectSnapshot: ObjectSnapshot
  };
});
