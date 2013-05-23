// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('cc.layer_tree_host_impl_view');

base.require('cc.constants');
base.require('cc.layer_tree_host_impl');
base.require('cc.picture');
base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');
base.require('ui.drag_handle');
base.require('ui.list_view');
base.require('ui.quad_stack');
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
        labelEl.textContent = layerInfo.name + ' ' +
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

  /**
   * @constructor
   */
  var LayerViewer = ui.define('layer-viewer');

  LayerViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layer_ = undefined;

      this.controls_ = document.createElement('top-controls');
      this.quadStack_ = new ui.QuadStack();
      this.appendChild(this.controls_);
      this.appendChild(this.quadStack_);

      this.statusEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.statusEL_.textContent = 'Selected layer';
      if (!cc.PictureSnapshot.CanRasterize()) {
        var tmp = this.statusEL_.appendChild(ui.createSpan('[WARNING!!!]'));
        tmp.style.paddingLeft = '10px';
        tmp.style.paddingRight = '10px';
        tmp.style.color = 'red';
        tmp.style.fontWeight = 'bold';
        tmp.title = cc.PictureSnapshot.HowToEnableRasterizing();
      }

      this.warningEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.warningEL_.textContent = '';

      this.scale_ = 0.0625;
      var scaleSelector = ui.createSelector(
          this, 'scale',
          [{label: '6.25%', value: 0.0625},
           {label: '12.5%', value: 0.125},
           {label: '25%', value: 0.25},
           {label: '50%', value: 0.5},
           {label: '75%', value: 0.75},
           {label: '100%', value: 1},
           {label: '200%', value: 2}
          ]);
      scaleSelector.selectedIndex = 3;
      this.scale_ = 0.5;
      this.controls_.appendChild(scaleSelector);

      this.showOtherLayers_ = true;
      var showOtherLayersCheckbox = ui.createCheckBox(
          this, 'showOtherLayers', 'Show other layers');
      this.controls_.appendChild(showOtherLayersCheckbox);

      this.showInvalidations_ = true;
      var showInvalidationsCheckbox = ui.createCheckBox(
          this, 'showInvalidations', 'Show invalidations');
      this.controls_.appendChild(showInvalidationsCheckbox);

      this.showContents_ = true;
      var showContentsCheckbox = ui.createCheckBox(
          this, 'showContents', 'Show contents');
      this.controls_.appendChild(showContentsCheckbox);
    },

    get layer() {
      return this.layer_;
    },

    set layer(layer) {
      this.layer_ = layer;
      this.scheduleUpdateContents_();
    },

    get scale() {
      return this.scale_;
    },

    set scale(scale) {
      this.scale_ = scale;
      this.scheduleUpdateContents_();
    },

    get showOtherLayers() {
      return this.showOtherLayers_;
    },

    set showOtherLayers(show) {
      this.showOtherLayers_ = show;
      this.updateContents_();
    },

    get showContents() {
      return this.showContents_;
    },

    set showContents(show) {
      this.showContents_ = show;
      this.updateContents_();
    },

    get showInvalidations() {
      return this.showInvalidations_;
    },

    set showInvalidations(show) {
      this.showInvalidations_ = show;
      this.updateContents_();
    },

    set highlightedTile(tileSnapshot) {
      this.highlightedTile_ = tileSnapshot;
      this.updateContents_();
    },

    scheduleUpdateContents_: function() {
      if (this.updateContentsPending_)
        return;
      this.updateContentsPending_ = true;
      webkitRequestAnimationFrame(this.updateContents_.bind(this));
    },

    updateContents_: function() {
      this.updateContentsPending_ = false;
      this.warningEL_.textContent = '';

      if (!this.layer_) {
        this.quadStack_.quads = [];
        return;
      }

      var selectedLayer = this.layer_;
      var showOtherLayers = this.showOtherLayers_;

      var layerTreeImpl = selectedLayer.layerTreeImpl;
      var lthi = layerTreeImpl.layerTreeHostImpl;
      var lthiInstance = lthi.objectInstance;
      var layers = [];
      if (showOtherLayers)
        layers = layerTreeImpl.renderSurfaceLayerList;
      else
        layers = [selectedLayer];

      // Figure out if we can draw the quads yet...
      if (this.showContents_) {
        var hadMissingPicture = false;
        for (var i = 0; i < layers.length; i++) {
          var layer = layers[i];
          for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
            var picture = layer.pictures[ir];
            if (picture.image ||
                !cc.PictureSnapshot.CanRasterize() ||
                !picture.layerRect)
              continue;
            picture.beginRenderingImage(
                this.scheduleUpdateContents_.bind(this));
            hadMissingPicture = true;
          }
        }
        if (hadMissingPicture)
          return;
      }

      // Generate the quads for the view.
      var quads = [];
      for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var layerQuad;
        layerQuad = layer.layerQuad.clone();

        // Generate image quads for the layer
        var hasMissing = false;
        for (var ir = layer.pictures.length - 1; ir >= 0; ir--) {
          var picture = layer.pictures[ir];
          if (!picture.layerRect) {
            hasMissing = true;
            continue;
          }
          var unitRect = picture.layerRect.asUVRectInside(layer.bounds);
          var iq = layerQuad.projectUnitRect(unitRect);

          if (picture.image && this.showContents_)
            iq.backgroundImage = picture.image;
          else
            iq.backgroundColor = 'rgba(0,0,0,0.1)';

          iq.stackingGroupId = i;
          quads.push(iq);
        }

        if (hasMissing)
          this.warningEL_.textContent = 'Missing pictures';

        // Generate the invalidation rect quads.
        if (this.showInvalidations_) {
          for (var ir = 0; ir < layer.invalidation.rects.length; ir++) {
            var rect = layer.invalidation.rects[ir];
            var unitRect = rect.asUVRectInside(layer.bounds);
            var iq = layerQuad.projectUnitRect(unitRect);
            iq.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            iq.borderColor = 'rgba(255, 0, 0, 1)';
            iq.stackingGroupId = i;
            quads.push(iq);
          }
        }

        // Push the layer quad last.
        layerQuad.borderColor = 'rgba(0,0,0,0.75)';
        layerQuad.stackingGroupId = i;
        quads.push(layerQuad);
        if (selectedLayer == layer && showOtherLayers)
          layerQuad.upperBorderColor = 'rgb(156,189,45)';
      }

      if (this.highlightedTile_) {
        var whichTree = layerTreeImpl.whichTree;
        var priority = whichTree == constants.ACTIVE_TREE ?
            this.highlightedTile_.args.activePriority :
            this.highlightedTile_.args.pendingPriority;
        var quad = priority.currentScreenQuad;
        var quadForDrawing = quad.clone();
        quadForDrawing.backgroundColor = 'rgba(0, 255, 0, 0.2)';
        quadForDrawing.borderColor = 'rgba(0, 255, 0, 1)';
        quadForDrawing.stackingGroupId = i;
        quads.push(quadForDrawing);
      }

      this.quadStack_.quads = quads;
      this.quadStack_.viewport = new ui.QuadViewViewport(
          lthiInstance.allLayersBBox, this.scale_);
      this.quadStack_.deviceViewportSizeForFrame = lthi.deviceViewportSize;
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
