// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_picker');

base.require('cc.constants');
base.require('cc.layer_tree_host_impl');
base.require('tracing.analysis.generic_object_view');
base.require('ui.drag_handle');
base.require('ui.list_view');
base.require('ui.dom_helpers');

base.exportTo('cc', function() {
  var constants = cc.constants;

  /**
   * @constructor
   */
  var LayerPicker = ui.define('layer-picker');

  LayerPicker.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.lthi_ = undefined;
      this.controls_ = document.createElement('top-controls');


      this.layerList_ = new ui.ListView();
      this.layerDataView_ = new tracing.analysis.GenericObjectView();
      this.appendChild(this.controls_);

      this.appendChild(this.layerList_);
      var dragHandle = new ui.DragHandle();
      dragHandle.horizontal = true;
      dragHandle.target = this.layerDataView_;
      this.appendChild(dragHandle);
      this.appendChild(this.layerDataView_);

      this.layerList_.addEventListener(
          'selection-changed', this.onLayerSelectionChanged_.bind(this));

      this.titleEl_ = document.createElement('span');
      this.controls_.appendChild(this.titleEl_);

      this.controls_.appendChild(ui.createSelector(
          this, 'whichTree',
          'layerPicker.whichTree', constants.ACTIVE_TREE,
          [{label: 'Active tree', value: constants.ACTIVE_TREE},
           {label: 'Pending tree', value: constants.PENDING_TREE}]));

      this.hidePureTransformLayers_ = true;
      this.controls_.appendChild(ui.createCheckBox(
          this, 'hidePureTransformLayers', 'Hide transform layers'));
    },

    get lthiSnapshot() {
      return this.lthiSnapshot_;
    },

    set lthiSnapshot(lthiSnapshot) {
      this.lthiSnapshot_ = lthiSnapshot;
      this.updateContents_();
    },

    get whichTree() {
      return this.whichTree_;
    },

    set whichTree(whichTree) {
      this.whichTree_ = whichTree;
      this.updateContents_();
    },

    get hidePureTransformLayers() {
      return this.hidePureTransformLayers_;
    },

    set hidePureTransformLayers(hide) {
      this.hidePureTransformLayers_ = hide;
      this.updateContents_();
    },

    getLayerInfos_: function() {
      if (!this.lthiSnapshot_)
        return [];

      var tree = this.lthiSnapshot_.getTree(this.whichTree_);
      if (!tree)
        return [];

      var layerInfos = [];

      var hidePureTransformLayers = this.hidePureTransformLayers_;

      function isPureTransformLayer(layer) {
        if (layer.args.compositingReasons &&
            layer.args.compositingReasons.length != 1 &&
            layer.args.compositingReasons[0] != 'No reasons given')
          return false;

        if (layer.args.drawsContent)
          return false;

        return true;
      }
      function visitLayer(layer, depth, note) {
        var info = {layer: layer,
          depth: depth};

        if (layer.args.drawsContent)
          info.name = layer.objectInstance.name;
        else
          info.name = 'cc::LayerImpl';

        if (!hidePureTransformLayers || !isPureTransformLayer(layer))
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
      var oldSelectedLayer = this.selectedLayer;
      this.updateContentsInner_();

      if (!oldSelectedLayer) {
        if (!this.layerList_.selectedElement) {
          // Try to select the first layer that drawsContent.
          for (var i = 0; i < this.layerList_.children.length; i++) {
            if (this.layerList_.children[i].layer.args.drawsContent) {
              this.layerList_.children[i].selected = true;
              return;
            }
          }
          // Barring that, select the first layer.
          if (this.layerList_.children.length > 0)
            this.layerList_.children[0].selected = true;
        }
        return;
      }

      // Try to resync the selection to what it was before.
      var goal = oldSelectedLayer.objectInstance;
      for (var i = 0; i < this.layerList_.children.length; i++) {
        if (this.layerList_.children[i].layer.objectInstance == goal) {
          this.layerList_.children[i].selected = true;
          return;
        }
      }

      // TODO(nduca): If matching failed, try to match on layer_id. The instance
      // may have changed but the id could persist.
    },

    updateContentsInner_: function() {
      if (this.lthiSnapshot_) {
        this.titleEl_.textContent = 'CC::LayerTreeHostImpl ' +
            this.lthiSnapshot_.objectInstance.id;
      } else {
        this.titleEl_.textContent = '<no tree chosen>';
      }

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
        var id;
        if (layer.args.layerId !== undefined)
          id = layer.args.layerId;
        else
          id = layer.objectInstance.id;
        labelEl.textContent = layerInfo.name + ' ' + id;


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
      if (this.selectedLayer)
        this.layerDataView_.object = this.selectedLayer.args;
      else
        this.layerDataView_.object = '<no layer selected>';
    },

    get selectedLayer() {
      if (!this.layerList_.selectedElement)
        return undefined;
      return this.layerList_.selectedElement.layer;
    }
  };

  return {
    LayerPicker: LayerPicker
  };
});
