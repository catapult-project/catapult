// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.model.object_instance');
base.require('cc.util');

base.exportTo('tcmalloc', function() {
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

    // TODO(jamescook): This seems to be called before the green dot is clicked.
    // Consider doing it in heap_view.js.
    initialize: function() {
      if (this.args.length == 0)
        throw new Error('No heap snapshot data.');

      // The first entry is total allocations across all stack traces.
      this.total_ = this.args[0];
      // The rest is a list of allocations.
      var allocs = this.args.slice(1);

      // Build a nested dictionary of trace event names.
      this.heap_ = {
        children: {},
        currentBytes: 0,
        currentAllocs: 0,
        totalBytes: 0,
        totalAllocs: 0
      };
      for (var i = 0; i < allocs.length; i++) {
        var alloc = allocs[i];
        var traceNames = alloc.trace.split(' ');
        var heapEntry = this.heap_;
        // Walk down into the heap of stack traces.
        for (var j = 0; j < traceNames.length; j++) {
          // Add up the total memory for intermediate entries, so the top of
          // each subtree is the total memory for that tree.
          heapEntry.totalBytes += alloc.totalBytes;
          heapEntry.totalAllocs += alloc.totalAllocs;
          // Look for existing children with this trace.
          var traceName = traceNames[j];
          if (!heapEntry.children[traceName]) {
            // New trace entry at this depth, so create a child for it.
            heapEntry.children[traceName] = {
              children: {},
              currentBytes: alloc.currentBytes,
              currentAllocs: alloc.currentAllocs,
              totalBytes: alloc.totalBytes,
              totalAllocs: alloc.totalAllocs
            };
          }
          // Descend into the children.
          heapEntry = heapEntry.children[traceName];
        }
      }
    }

  };

  ObjectSnapshot.register('memory::Heap', HeapSnapshot);

  return {
    HeapSnapshot: HeapSnapshot
  };
});
