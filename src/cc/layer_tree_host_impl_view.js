// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_tree_host_impl_view');

base.require('cc.layer_tree_host_impl');
base.require('cc.layer_picker');
base.require('cc.layer_viewer');
base.require('tracing.analysis.object_snapshot_view');
base.require('ui.drag_handle');

base.exportTo('cc', function() {
  /*
   * Displays a LayerTreeHostImpl snapshot in a human readable form.
   * @constructor
   */
  var LayerTreeHostImplSnapshotView = ui.define(
      tracing.analysis.ObjectSnapshotView);

  LayerTreeHostImplSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('lthi-s-view');

      this.layerPicker_ = new cc.LayerPicker();
      this.layerPicker_.addEventListener(
          'selection-changed',
          this.onLayerSelectionChanged_.bind(this));

      this.dragHandle_ = new ui.DragHandle();
      this.dragHandle_.horizontal = false;
      this.dragHandle_.target = this.layerPicker_;

      this.layerViewer_ = new cc.LayerViewer();
      this.appendChild(this.layerPicker_);
      this.appendChild(this.dragHandle_);
      this.appendChild(this.layerViewer_);
    },

    onLayerSelectionChanged_: function() {
      this.layerViewer_.layer = this.layerPicker_.selectedLayer;
    },

    updateContents: function() {
      var snapshot = this.objectSnapshot;
      var instance = snapshot.objectInstance;
      this.layerPicker_.lthiSnapshot = snapshot;
      this.layerViewer_.layer = this.layerPicker_.selectedLayer;
    },

    set highlightedTile(tileSnapshot) {
      this.layerViewer_.highlightedTile = tileSnapshot;
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'cc::LayerTreeHostImpl', LayerTreeHostImplSnapshotView);

  return {
    LayerTreeHostImplSnapshotView: LayerTreeHostImplSnapshotView
  };
});
