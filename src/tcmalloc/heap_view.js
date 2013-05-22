// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tcmalloc.heap_view');

base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('cc', function() {

  var tsRound = tracing.analysis.tsRound;

  /*
   * Displays a picture snapshot in a human readable form.
   * @constructor
   */
  var HeapSnapshotView = ui.define(
      tracing.analysis.ObjectSnapshotView);

  HeapSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('heap-snapshot-view');
    },

    updateContents: function() {
      var heap = this.objectSnapshot_;
      if (!heap) {
        this.textContent = '';
        return;
      }
      this.textContent = 'Heap at ' + tsRound(heap.ts) + ' with ' +
          heap.allocs.length + ' allocations';

      // TODO(jamescook): Do something interesting here.
      var myDiv = document.createElement('div');
      myDiv.textContent = 'blah';
      this.appendChild(myDiv);
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'memory::Heap', HeapSnapshotView);

  return {
    HeapSnapshotView: HeapSnapshotView
  };

});
