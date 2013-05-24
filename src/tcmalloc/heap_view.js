// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tcmalloc.heap_view');

base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('tcmalloc', function() {

  var tsRound = tracing.analysis.tsRound;

  /*
   * Displays a heap memory snapshot in a human readable form.
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
      var snapshot = this.objectSnapshot_;
      if (!snapshot || !snapshot.heap_) {
        this.textContent = 'No heap found.';
        return;
      }
      // Clear old snapshot view.
      this.textContent = '';

      var subhead = document.createElement('div');
      subhead.textContent =
          this.getByteString_(snapshot.total_.totalBytes) + ' in ' +
              snapshot.total_.totalAllocs + ' allocations';
      this.appendChild(subhead);

      // Build a nested tree-view of allocations
      var myList = this.buildAllocList_(snapshot.heap_, false);
      this.appendChild(myList);
    },

    /*
     * Returns a <ul> with a nested list with clickable entries.
     */
    buildAllocList_: function(heapEntry, hide) {
      var myList = document.createElement('ul');
      myList.hidden = hide;
      var keys = Object.keys(heapEntry.children);
      keys.sort(function(a, b) {
        // Sort from large to small.
        return heapEntry.children[b].totalBytes -
            heapEntry.children[a].totalBytes;
      });
      for (var i = 0; i < keys.length; i++) {
        var traceName = keys[i];
        var trace = heapEntry.children[traceName];
        var myItem = this.buildItem_(traceName, trace.totalBytes);
        myList.appendChild(myItem);
        // Build a nested <ul> list of my children.
        if (Object.keys(trace.children).length > 0)
          myItem.appendChild(this.buildAllocList_(trace, true));
      }
      return myList;
    },

    /*
     * Returns a <li> for an allocation traceName of size bytes.
     */
    buildItem_: function(traceName, bytes) {
      var myItem = document.createElement('li');
      myItem.addEventListener('click', function(event) {
        // Allow click on the +/- image (li) or child divs.
        if (this == event.target || this == event.target.parentElement) {
          this.classList.toggle('expanded');
          var child = this.querySelector('ul');
          child.hidden = !child.hidden;
        }
      });
      myItem.classList.add('collapsed');

      var byteDiv = document.createElement('div');
      byteDiv.textContent = this.getByteString_(bytes);
      byteDiv.className = 'trace-bytes';
      myItem.appendChild(byteDiv);

      var traceDiv = document.createElement('div');
      traceDiv.textContent = traceName;
      traceDiv.className = 'trace-name';
      myItem.appendChild(traceDiv);

      return myItem;
    },

    /*
     * Returns a human readable string for a size in bytes.
     */
    getByteString_: function(bytes) {
      var mb = bytes / 1024 / 1024;
      return Math.round(mb * 10) / 10 + ' MB';
    },
  };

  tracing.analysis.ObjectSnapshotView.register(
      'memory::Heap', HeapSnapshotView);

  return {
    HeapSnapshotView: HeapSnapshotView
  };

});
