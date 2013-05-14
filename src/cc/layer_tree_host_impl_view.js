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


      this.layerContextViewer_ = new LayerContextViewer();
      this.addEventListener('selection-changed', function() {
        this.layerContextViewer_.layer = this.selectedLayer;
      }.bind(this));

      this.layerList_ = new ui.ListView();
      this.layerDataView_ = new tracing.analysis.GenericObjectView();
      this.appendChild(this.controls_);

      var layerListAndContext = document.createElement('list-and-context');
      layerListAndContext.appendChild(this.layerContextViewer_);
      layerListAndContext.appendChild(this.layerList_);

      this.appendChild(layerListAndContext);
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
    },

    get lthiSnapshot() {
      return this.lthiSnapshot_;
    },

    set lthiSnapshot(lthiSnapshot) {
      var oldSelectedLayer = this.selectedLayer;
      this.lthiSnapshot_ = lthiSnapshot;
      this.updateContents_();

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
      if (!tree)
        return [];

      var layerInfos = [];
      function visitLayer(layer, depth, note) {
        var info = {layer: layer,
          depth: depth};
        if (layer.args.drawsContent)
          info.name = layer.objectInstance.name;
        else
          info.name = 'cc::LayerImpl';
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
        this.layerDataView_.object = "<no layer selected>";
    },

    get selectedLayer() {
      if (!this.layerList_.selectedElement)
        return undefined;
      return this.layerList_.selectedElement.layer;
    }
  };

  /**
   * Shows a layer and all its related layers.
   * @constructor
   */
  var LayerContextViewer = ui.define('layer-context-viewer');

  LayerContextViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.layer_ = undefined;
      this.lastLthiInstance_ = undefined;

      this.quadView_ = new ui.QuadView();
      this.appendChild(this.quadView_);

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

        var selected = layer == this.layer;
        q.selected = selected;
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
      var viewport = new ui.QuadViewViewport(lthiInstance.allLayersBBox, 0.075);
      this.quadView_.quads = this.getTreeQuads();
      this.quadView_.viewport = viewport;
      this.quadView_.deviceViewportSizeForFrame = lthi.deviceViewportSize;
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
      this.quadView_ = new ui.QuadView();
      this.appendChild(this.controls_);
      this.appendChild(this.quadView_);

      this.statusEL_ = this.controls_.appendChild(ui.createSpan(''));
      this.statusEL_.textContent = 'Selected layer';
      if (!cc.PictureSnapshot.CanRasterize()) {
        var tmp = this.statusEL_.appendChild(ui.createSpan('[WARNING!!!]'));
        tmp.style.paddingLeft = '10px';
        tmp.style.paddingRight = '10px';
        tmp.style.color = 'red';
        tmp.style.fontWeight = 'bold';
        tmp.title = cc.PictureSnapshot.HowToEnableRasterizing()
      }

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
    },

    get layer() {
      return this.layer_;
    },

    set layer(layer) {
      this.layer_ = layer;
      this.updateContents_();
    },

    get scale() {
      return this.scale_;
    },

    set scale(scale) {
      this.scale_ = scale;
      this.updateContents_();
    },

    updateContents_: function() {
      if (!this.layer_) {
        this.quadView_.quads = [];
        return;
      }
      var layer = this.layer_;
      var quads = [];

      // Picture quads
      for (var ir = 0; ir < layer.pictures.length; ir++) {
        var picture = layer.pictures[ir];
        var rect = picture.layerRect;
        var iq = base.QuadFromRect(rect);
        var rd = picture.getRasterData();
        if (rd)
          iq.backgroundRasterData = rd;
        else
          iq.backgroundColor = 'rgba(0, 0, 0, 0.15)';
        iq.borderColor = 'rgba(0, 0, 0, .5)';
        quads.push(iq);
      }

      // Invalidaiton quads
      for (var ir = 0; ir < layer.invalidation.rects.length; ir++) {
        var rect = layer.invalidation.rects[ir];
        var iq = base.QuadFromRect(rect);
        iq.backgroundColor = 'rgba(255, 0, 0, 0.05)';
        iq.borderColor = 'rgba(255, 0, 0, 1)';
        quads.push(iq);
      }

      var quads_bbox = new base.BBox2();
      quads_bbox.addXY(0, 0);
      quads_bbox.addXY(layer.bounds.width, layer.bounds.height);

      this.quadView_.quads = quads;
      this.quadView_.viewport = new ui.QuadViewViewport(quads_bbox, this.scale_);
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
