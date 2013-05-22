// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.model.object_instance');
base.require('cc.util');

base.exportTo('memory', function() {
  var ObjectSnapshot = tracing.model.ObjectSnapshot;

  /**
   * @constructor
   */
  function HeapSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  HeapSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);

      // TODO(jamescook): Any generic field setup can go here.
    },

    initialize: function() {
      if (this.args.length == 0)
        throw new Error('Omgbbq');
      this.totals = this.args[0];
      this.allocs = this.args.slice(1);
    }

  };

  ObjectSnapshot.register('memory::Heap', HeapSnapshot);

  return {
    HeapSnapshot: HeapSnapshot
  };
});
