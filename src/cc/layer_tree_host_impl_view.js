// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_tree_host_impl_view');

base.require('cc.constants');
base.require('cc.layer_tree_host_impl');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');
base.require('ui.list_view');
base.require('ui.quad_view');
base.exportTo('cc', function() {
  var constants = cc.constants;
  var tsRound = tracing.analysis.tsRound;

  /**
   * @constructor
   */
  var LayerPicker = ui.define('layer-picker');

  LayerPicker.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.lthi_ = undefined;
      this.whichTree_ = constants.ACTIVE_TREE;

      this.controls_ = document.createElement('top-controls');
      this.layerList_ = new ui.ListView();
      this.appendChild(this.controls_);
      this.appendChild(this.layerList_);
      this.layerList_.addEventListener(
          'selection-changed', this.onLayerSelectionChanged_.bind(this));

      this.titleEl_ = document.createElement('span');
      this.controls_.appendChild(this.titleEl_);

      this.controls_.appendChild(ui.createSelector(
          this, 'whichTree',
          [{label: 'Active tree', value: constants.ACTIVE_TREE},
           {label: 'Pending tree', value: constants.ACTIVE_TREE}]));
    },

    get lthiSnapshot() {
      return this.lthiSnapshot_;
    },

    set lthiSnapshot(lthiSnapshot) {
      var oldSelectedLayer = this.selectedLayer;
      this.lthiSnapshot_ = lthiSnapshot;
      this.updateContents_();

      if (!oldSelectedLayer) {
        if (!this.layerList_.selectedElement)
          this.layerList_.children[0].selected = true;
        return;
      }

      // Try to resync the selection to what it was before.
      var goal = oldSelectedLayer.objectInstance;
      for (var i = 0; i < this.layerList_.children.length; i++) {
        if (this.layerList_.children[i].layer.objectInstance == goal) {
          this.layerList_.children[i].selected = true;
          break;
        }
      }
    },

    get whichTree() {
      return this.whichTree_;
    },

    set whichTree(whichTree) {
      this.whichTree_ = whichTree;
      this.updateContents_();
    },

    getLayerInfos_: function() {
      if (!this.lthiSnapshot_)
        return [];

      var tree = this.lthiSnapshot_.getTree(this.whichTree_);
      var layerInfos = [];
      function visitLayer(layer, depth, note) {
        var info = {layer: layer,
          depth: depth};
        layerInfos.push(info);

        var childInfo;
        for (var i = 0; i < layer.children.length; i++)
          visitLayer(layer.children[i], depth + 1);

        if (layer.maskLayer) {
          childInfo = visitLayer(layer.maskLayer, depth + 2);
          childInfo.isMaskLayer = true;
        }

        if (layer.replicaLayer) {
          var childInfo = visitLayer(layer.replicaLayer, depth + 2);
          childInfo.replicaLayer = true;
        }

        return info;
      };
      visitLayer(tree.rootLayer, 0);
      return layerInfos;
    },

    updateContents_: function() {
      this.titleEl_.textContent = 'CC::LayerTreeHostImpl ' +
          this.lthiSnapshot_.objectInstance.id;
      this.layerList_.clear();

      var layerInfos = this.getLayerInfos_();
      layerInfos.forEach(function(layerInfo) {
        var layer = layerInfo.layer;

        var item = document.createElement('div');

        var indentEl = item.appendChild(ui.createSpan());
        indentEl.style.whiteSpace = 'pre';
        for (var i = 0; i < layerInfo.depth; i++)
          indentEl.textContent = indentEl.textContent + ' ';

        var labelEl = item.appendChild(ui.createSpan());
        labelEl.textContent = layer.objectInstance.name + ' ' +
            layer.objectInstance.id;

        var notesEl = item.appendChild(ui.createSpan());
        if (layerInfo.isMaskLayer)
          notesEl.textContent += '(mask)';
        if (layerInfo.isReplicaLayer)
          notesEl.textContent += '(replica)';

        item.layer = layer;
        this.layerList_.appendChild(item);
      }, this);
    },

    onLayerSelectionChanged_: function(e) {
      base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    get selectedLayer() {
      if (!this.layerList_.selectedElement)
        return undefined;
      return this.layerList_.selectedElement.layer;
    }
  };

  /**
   * @constructor
   */
  var LayerViewer = ui.define('layer-viewer');

  LayerViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layer_ = undefined;
      this.lastLthiInstance_ = undefined;

      this.controls_ = document.createElement('top-controls');
      this.quadView_ = new ui.QuadView();
      this.appendChild(this.controls_);
      this.appendChild(this.quadView_);

      this.statusEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.statusEL_.textContent = '<various options go here eventually>';
    },

    get layer() {
      return this.layer_;
    },

    set layer(layer) {
      this.layer_ = layer;
      this.updateContents_();
    },

    getTreeQuads: function() {
      var layerTreeImpl = this.layer_.layerTreeImpl;
      var rsll = layerTreeImpl.renderSurfaceLayerList;
      var quads = [];
      for (var i = 0; i < rsll.length; i++) {
        var layer = rsll[i];
        var q = layer.layerQuad.copy();
        quads.push(q);
        if (layer == this.layer)
          q.selected = true;
      }
      return quads;
    },

    updateContents_: function() {
      if (!this.layer_) {
        this.quadView_.quads = [];
        return;
      }

      var lthi = this.layer_.layerTreeImpl.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;
      var viewport = new ui.QuadViewViewport(lthiInstance.allLayersBBox, 0.15);
      this.quadView_.quads = this.getTreeQuads();
      this.quadView_.title = 'layer' + this.layer_.objectInstance.id;
      this.quadView_.viewport = viewport;
      this.quadView_.deviceViewportSizeForFrame = lthi.deviceViewportSize;
    }
  };


  /*
   * displays a LayerTreeHostImpl snapshot in a human readable form.
   * @constructor
   */
  var LayerTreeHostImplSnapshotView = ui.define(
      tracing.analysis.ObjectSnapshotView);

  LayerTreeHostImplSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('lthi-s-view');

      this.layerPicker_ = new LayerPicker();
      this.layerPicker_.addEventListener(
          'selection-changed',
          this.onLayerSelectionChanged_.bind(this));

      this.dragHandle_ = new ui.DragHandle();
      this.dragHandle_.horizontal = false;
      this.dragHandle_.target = this.layerPicker_;

      this.layerViewer_ = new LayerViewer();
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
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'cc::LayerTreeHostImpl', LayerTreeHostImplSnapshotView);

  return {
    LayerTreeHostImplSnapshotView: LayerTreeHostImplSnapshotView
  };
});
