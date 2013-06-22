// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_picker');

base.require('cc.constants');
base.require('cc.layer_tree_host_impl');
base.require('cc.selection');
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
      this.appendChild(this.controls_);

      this.appendChild(this.layerList_);

      this.layerList_.addEventListener(
          'selection-changed', this.onLayerSelectionChanged_.bind(this));

      this.controls_.appendChild(ui.createSelector(
          this, 'whichTree',
          'layerPicker.whichTree', constants.ACTIVE_TREE,
          [{label: 'Active tree', value: constants.ACTIVE_TREE},
           {label: 'Pending tree', value: constants.PENDING_TREE}]));

      this.hidePureTransformLayers_ = true;
      var hideTransformLayers = ui.createCheckBox(
          this, 'hidePureTransformLayers',
          'layerPicker.hideTransformLayers', true,
          'Hide transform layers');
      hideTransformLayers.classList.add('hide-transform-layers');
      this.controls_.appendChild(hideTransformLayers);
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
      function visitLayer(layer, depth, isMask, isReplica) {
        var info = {layer: layer,
          depth: depth};

        if (layer.args.drawsContent)
          info.name = layer.objectInstance.name;
        else
          info.name = 'cc::LayerImpl';

        info.isMaskLayer = isMask;
        info.replicaLayer = isReplica;

        if (!hidePureTransformLayers || !isPureTransformLayer(layer))
          layerInfos.push(info);

      };
      tree.iterLayers(visitLayer);
      return layerInfos;
    },

    updateContents_: function() {
      this.layerList_.clear();

      var selectedLayerId;
      if (this.selection_ && this.selection_.associatedLayerId)
        selectedLayerId = this.selection_.associatedLayerId;

      var layerInfos = this.getLayerInfos_();
      layerInfos.forEach(function(layerInfo) {
        var layer = layerInfo.layer;

        var item = document.createElement('div');

        var indentEl = item.appendChild(ui.createSpan());
        indentEl.style.whiteSpace = 'pre';
        for (var i = 0; i < layerInfo.depth; i++)
          indentEl.textContent = indentEl.textContent + ' ';

        var labelEl = item.appendChild(ui.createSpan());
        var id = layer.layerId;
        labelEl.textContent = layerInfo.name + ' ' + id;


        var notesEl = item.appendChild(ui.createSpan());
        if (layerInfo.isMaskLayer)
          notesEl.textContent += '(mask)';
        if (layerInfo.isReplicaLayer)
          notesEl.textContent += '(replica)';

        item.layer = layer;
        this.layerList_.appendChild(item);

        if (layer.layerId == selectedLayerId)
          layer.selected = true;
      }, this);
    },

    onLayerSelectionChanged_: function(e) {
      var selectedLayer;
      if (this.layerList_.selectedElement)
        selectedLayer = this.layerList_.selectedElement.layer;

      if (selectedLayer)
        this.selection_ = new cc.LayerSelection(selectedLayer);
      else
        this.selection_ = undefined;
      base.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    get selection() {
      return this.selection_;
    },

    set selection(selection) {
      this.selection_ = selection;
      this.updateContents_();
    }
  };

  return {
    LayerPicker: LayerPicker
  };
});
