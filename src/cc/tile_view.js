// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.tile');
base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('cc', function() {

  /*
   * Displays a tile in a human readable form.
   * @constructor
   */
  var TileSnapshotView = ui.define(
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
