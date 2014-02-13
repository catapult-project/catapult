// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('cc.tile');
tvcm.require('tracing.analysis.generic_object_view');
tvcm.require('tracing.analysis.object_snapshot_view');
tvcm.require('tracing.analysis.util');

tvcm.exportTo('cc', function() {

  /*
   * Displays a tile in a human readable form.
   * @constructor
   */
  var TileSnapshotView = tvcm.ui.define(
      'tile-snapshot-view',
      tracing.analysis.ObjectSnapshotView);

  TileSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('tile-snapshot-view');
      this.layerTreeView_ = new cc.LayerTreeHostImplSnapshotView();
      this.appendChild(this.layerTreeView_);
    },

    updateContents: function() {
      var tile = this.objectSnapshot_;
      var layerTreeHostImpl = tile.containingSnapshot;
      if (!layerTreeHostImpl)
        return;

      this.layerTreeView_.objectSnapshot = layerTreeHostImpl;
      this.layerTreeView_.selection = new cc.TileSelection(tile);
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'cc::Tile', TileSnapshotView, {
        showInTrackView: false
      });

  return {
    TileSnapshotView: TileSnapshotView
  };

});
