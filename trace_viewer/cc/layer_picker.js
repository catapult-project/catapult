// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('cc.layer_picker');

tvcm.require('cc.constants');
tvcm.require('cc.layer_tree_host_impl');
tvcm.require('cc.selection');
tvcm.require('tracing.analysis.generic_object_view');
tvcm.require('tracing.trace_model.event');
tvcm.require('tvcm.ui.drag_handle');
tvcm.require('tvcm.ui.list_view');
tvcm.require('tvcm.ui.dom_helpers');

tvcm.exportTo('cc', function() {
  var constants = cc.constants;
  var RENDER_PASS_QUADS =
      Math.max(constants.ACTIVE_TREE, constants.PENDING_TREE) + 1;

  /**
   * @constructor
   */
  var LayerPicker = tvcm.ui.define('layer-picker');

  LayerPicker.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.lthi_ = undefined;
      this.controls_ = document.createElement('top-controls');
      this.renderPassQuads_ = false;


      this.itemList_ = new tvcm.ui.ListView();
      this.appendChild(this.controls_);

      this.appendChild(this.itemList_);

      this.itemList_.addEventListener(
          'selection-changed', this.onItemSelectionChanged_.bind(this));

      this.controls_.appendChild(tvcm.ui.createSelector(
          this, 'whichTree',
          'layerPicker.whichTree', constants.ACTIVE_TREE,
          [{label: 'Active tree', value: constants.ACTIVE_TREE},
           {label: 'Pending tree', value: constants.PENDING_TREE},
           {label: 'Render pass quads', value: RENDER_PASS_QUADS}]));

      this.showPureTransformLayers_ = false;
      var showPureTransformLayers = tvcm.ui.createCheckBox(
          this, 'showPureTransformLayers',
          'layerPicker.showPureTransformLayers', false,
          'Transform layers');
      showPureTransformLayers.classList.add('show-transform-layers');
      showPureTransformLayers.title =
          'When checked, pure transform layers are shown';
      this.controls_.appendChild(showPureTransformLayers);
    },

    get lthiSnapshot() {
      return this.lthiSnapshot_;
    },

    set lthiSnapshot(lthiSnapshot) {
      this.lthiSnapshot_ = lthiSnapshot;
      this.updateContents_();
    },

    get whichTree() {
      return this.renderPassQuads_ ? constants.ACTIVE_TREE : this.whichTree_;
    },

    set whichTree(whichTree) {
      this.whichTree_ = whichTree;
      this.renderPassQuads_ = (whichTree == RENDER_PASS_QUADS);
      this.updateContents_();
      tvcm.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    get isRenderPassQuads() {
      return this.renderPassQuads_;
    },

    get showPureTransformLayers() {
      return this.showPureTransformLayers_;
    },

    set showPureTransformLayers(show) {
      if (this.showPureTransformLayers_ === show)
        return;
      this.showPureTransformLayers_ = show;
      this.updateContents_();
    },

    getRenderPassInfos_: function() {
      if (!this.lthiSnapshot_)
        return [];

      var renderPassInfo = [];
      if (!this.lthiSnapshot_.args.frame ||
          !this.lthiSnapshot_.args.frame.renderPasses)
        return renderPassInfo;

      var renderPasses = this.lthiSnapshot_.args.frame.renderPasses;
      for (var i = 0; i < renderPasses.length; ++i) {
        var info = {renderPass: renderPasses[i],
                     depth: 0,
                     id: i,
                     name: 'cc::RenderPass'};
        renderPassInfo.push(info);
      }
      return renderPassInfo;
    },

    getLayerInfos_: function() {
      if (!this.lthiSnapshot_)
        return [];

      var tree = this.lthiSnapshot_.getTree(this.whichTree_);
      if (!tree)
        return [];

      var layerInfos = [];

      var showPureTransformLayers = this.showPureTransformLayers_;

      function isPureTransformLayer(layer) {
        if (layer.args.compositingReasons &&
            layer.args.compositingReasons.length != 1 &&
            layer.args.compositingReasons[0] != 'No reasons given')
          return false;

        if (layer.args.drawsContent)
          return false;

        return true;
      }
      var visitedLayers = {};
      function visitLayer(layer, depth, isMask, isReplica) {
        if (visitedLayers[layer.layerId])
          return;
        visitedLayers[layer.layerId] = true;
        var info = {layer: layer,
          depth: depth};

        if (layer.args.drawsContent)
          info.name = layer.objectInstance.name;
        else
          info.name = 'cc::LayerImpl';

        if (layer.usingGpuRasterization)
          info.name += ' (G)';

        info.isMaskLayer = isMask;
        info.replicaLayer = isReplica;

        if (showPureTransformLayers || !isPureTransformLayer(layer))
          layerInfos.push(info);

      };
      tree.iterLayers(visitLayer);
      return layerInfos;
    },

    updateContents_: function() {
      if (this.renderPassQuads_)
        this.updateRenderPassContents_();
      else
        this.updateLayerContents_();

    },

    updateRenderPassContents_: function() {
      this.itemList_.clear();

      var selectedRenderPassId;
      if (this.selection_ && this.selection_.associatedRenderPassId)
        selectedRenderPassId = this.selection_.associatedRenderPassId;

      var renderPassInfos = this.getRenderPassInfos_();
      renderPassInfos.forEach(function(renderPassInfo) {
        var renderPass = renderPassInfo.renderPass;
        var id = renderPassInfo.id;

        var item = this.createElementWithDepth_(renderPassInfo.depth);
        var labelEl = item.appendChild(tvcm.ui.createSpan());

        labelEl.textContent = renderPassInfo.name + ' ' + id;
        item.renderPass = renderPass;
        item.renderPassId = id;
        this.itemList_.appendChild(item);

        if (id == selectedRenderPassId) {
          renderPass.selectionState =
              tracing.trace_model.SelectionState.SELECTED;
        }
      }, this);
    },

    updateLayerContents_: function() {
      this.itemList_.clear();

      var selectedLayerId;
      if (this.selection_ && this.selection_.associatedLayerId)
        selectedLayerId = this.selection_.associatedLayerId;

      var layerInfos = this.getLayerInfos_();
      layerInfos.forEach(function(layerInfo) {
        var layer = layerInfo.layer;
        var id = layer.layerId;

        var item = this.createElementWithDepth_(layerInfo.depth);
        var labelEl = item.appendChild(tvcm.ui.createSpan());

        labelEl.textContent = layerInfo.name + ' ' + id;

        var notesEl = item.appendChild(tvcm.ui.createSpan());
        if (layerInfo.isMaskLayer)
          notesEl.textContent += '(mask)';
        if (layerInfo.isReplicaLayer)
          notesEl.textContent += '(replica)';

        item.layer = layer;
        this.itemList_.appendChild(item);

        if (layer.layerId == selectedLayerId)
          layer.selectionState = tracing.trace_model.SelectionState.SELECTED;
      }, this);
    },

    createElementWithDepth_: function(depth) {
      var item = document.createElement('div');

      var indentEl = item.appendChild(tvcm.ui.createSpan());
      indentEl.style.whiteSpace = 'pre';
      for (var i = 0; i < depth; i++)
        indentEl.textContent = indentEl.textContent + ' ';
      return item;
    },

    onItemSelectionChanged_: function(e) {
      if (this.renderPassQuads_)
        this.onRenderPassSelected_(e);
      else
        this.onLayerSelected_(e);
      tvcm.dispatchSimpleEvent(this, 'selection-changed', false);
    },

    onRenderPassSelected_: function(e) {
      var selectedRenderPass;
      var selectedRenderPassId;
      if (this.itemList_.selectedElement) {
        selectedRenderPass = this.itemList_.selectedElement.renderPass;
        selectedRenderPassId =
            this.itemList_.selectedElement.renderPassId;
      }

      if (selectedRenderPass) {
        this.selection_ = new cc.RenderPassSelection(
            selectedRenderPass, selectedRenderPassId);
      } else {
        this.selection_ = undefined;
      }
    },

    onLayerSelected_: function(e) {
      var selectedLayer;
      if (this.itemList_.selectedElement)
        selectedLayer = this.itemList_.selectedElement.layer;

      if (selectedLayer)
        this.selection_ = new cc.LayerSelection(selectedLayer);
      else
        this.selection_ = undefined;
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
