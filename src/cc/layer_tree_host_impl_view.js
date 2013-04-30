// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_tree_host_impl_view');

base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');
base.exportTo('tracing.analysis', function() {
  var tsRound = tracing.analysis.tsRound;

  /*
   * Displays a LayerTreeHostImpl snapshot in a human readable form.
   * @constructor
   */
  var LayerTreeHostImplSnapshotView = ui.define(
      tracing.analysis.ObjectSnapshotView);

  LayerTreeHostImplSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('default-object-view');
    },

    updateContents: function() {
      var snapshot = this.objectSnapshot;
      if (!snapshot) {
        this.textContent = '';
        return;
      }
      var instance = snapshot.objectInstance;

      // TODO(nduca): Put something good here.
      this.textContent = 'CC::LayerTreeHostImpl Snapshot ' + snapshot.ts;
    },
  };


  tracing.analysis.ObjectSnapshotView.register(
    'cc::LayerTreeHostImpl', LayerTreeHostImplSnapshotView);

  return {
    LayerTreeHostImplSnapshotView: LayerTreeHostImplSnapshotView,
  };
});
