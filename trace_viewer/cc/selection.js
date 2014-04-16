// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.analysis.generic_object_view');
tvcm.require('tracing.analysis.analyze_selection');
tvcm.require('tracing.analysis.analysis_results');

tvcm.exportTo('cc', function() {
  var tsRound = tracing.analysis.tsRound;

  var GenericObjectViewWithLabel = tracing.analysis.GenericObjectViewWithLabel;

  function Selection() {
    this.selectionToSetIfClicked = undefined;
  };
  Selection.prototype = {
    /**
     * When two things are picked in the UI, one must occasionally tie-break
     * between them to decide what was really clicked. Things with higher
     * specicifity will win.
     */
    get specicifity() {
      throw new Error('Not implemented');
    },

    /**
     * If a selection is related to a specific layer, then this returns the
     * layerId of that layer. If the selection is not related to a layer, for
     * example if the device viewport is selected, then this returns undefined.
     */
    get associatedLayerId() {
      throw new Error('Not implemented');
    },

    /**
     * If a selection is related to a specific render pass, then this returns
     * the layerId of that layer. If the selection is not related to a layer,
     * for example if the device viewport is selected, then this returns
     * undefined.
     */
    get associatedRenderPassId() {
      throw new Error('Not implemented');
    },

    /**
     * If the selected item(s) is visible on the pending tree in a way that
     * should be highlighted, returns the quad for the item on the pending tree.
     * Otherwise, returns undefined.
     */
    get quadIfPending() {
      throw new Error('Not implemented');
    },

    /**
     * If the selected item(s) is visible on the active tree in a way that
     * should be highlighted, returns the quad for the item on the active tree.
     * Otherwise, returns undefined.
     */
    get quadIfActive() {
      throw new Error('Not implemented');
    },

    /**
     * A stable string describing what is selected. Used to determine a stable
     * color of the highlight quads for this selection.
     */
    get title() {
      throw new Error('Not implemented');
    },

    /**
     * Called when the selection is made active in the layer view. Must return
     * an HTMLElement that explains this selection in detail.
     */
    createAnalysis: function() {
      throw new Error('Not implemented');
    },

    /**
     * Should try to create the equivalent selection in the provided LTHI,
     * or undefined if it can't be done.
     */
    findEquivalent: function(lthi) {
      throw new Error('Not implemented');
    }
  };

  /**
   * @constructor
   */
  function RenderPassSelection(renderPass, renderPassId) {
    if (!renderPass || (renderPassId === undefined))
      throw new Error('Render pass (with id) is required');
    this.renderPass_ = renderPass;
    this.renderPassId_ = renderPassId;
  }

  RenderPassSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 1;
    },

    get associatedLayerId() {
      return undefined;
    },

    get associatedRenderPassId() {
      return this.renderPassId_;
    },

    get renderPass() {
      return this.renderPass_;
    },

    createAnalysis: function() {
      var dataView = new GenericObjectViewWithLabel();
      dataView.label = 'RenderPass ' + this.renderPassId_;
      dataView.object = this.renderPass_.args;
      return dataView;
    },

    get title() {
      return this.renderPass_.objectInstance.typeName;
    }
  };

  /**
   * @constructor
   */
  function LayerSelection(layer) {
    if (!layer)
      throw new Error('Layer is required');
    this.layer_ = layer;
  }

  LayerSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 1;
    },

    get associatedLayerId() {
      return this.layer_.layerId;
    },

    get associatedRenderPassId() {
      return undefined;
    },

    get quadIfPending() {
      return undefined;
    },

    get quadIfActive() {
      return undefined;
    },

    get layer() {
      return this.layer_;
    },

    createAnalysis: function() {
      var dataView = new GenericObjectViewWithLabel();
      dataView.label = 'Layer ' + this.layer_.layerId;
      if (this.layer_.usingGpuRasterization)
        dataView.label += ' (GPU-rasterized)';
      dataView.object = this.layer_.args;
      return dataView;
    },

    get title() {
      return this.layer_.objectInstance.typeName;
    },

    findEquivalent: function(lthi) {
      var layer = lthi.activeTree.findLayerWithId(this.layer_.layerId) ||
          lthi.pendingTree.findLayerWithId(this.layer_.layerId);
      if (!layer)
        return undefined;
      return new LayerSelection(layer);
    }
  };

  /**
   * @constructor
   */
  function TileSelection(tile) {
    this.tile_ = tile;
  }

  TileSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 2;
    },

    get associatedLayerId() {
      return this.tile_.layerId;
    },

    get layerRect() {
      return this.tile_.layerRect;
    },

    createAnalysis: function() {
      var analysis = new GenericObjectViewWithLabel();
      analysis.label = 'Tile ' + this.tile_.objectInstance.id + ' on layer ' +
          this.tile_.layerId;
      analysis.object = this.tile_.args;
      return analysis;
    },

    get title() {
      return this.tile_.objectInstance.typeName;
    },

    findEquivalent: function(lthi) {
      var tileInstance = this.tile_.tileInstance;
      if (lthi.ts < tileInstance.creationTs ||
          lthi.ts >= tileInstance.deletionTs)
        return undefined;
      var tileSnapshot = tileInstance.getSnapshotAt(lthi.ts);
      if (!tileSnapshot)
        return undefined;
      return new TileSelection(tileSnapshot);
    }
  };

  /**
   * @constructor
   */
  function LayerRectSelection(layer, rectType, rect, opt_data) {
    this.layer_ = layer;
    this.rectType_ = rectType;
    this.rect_ = rect;
    this.data_ = opt_data !== undefined ? opt_data : rect;
  }

  LayerRectSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 2;
    },

    get associatedLayerId() {
      return this.layer_.layerId;
    },

    get layerRect() {
      return this.rect_;
    },

    createAnalysis: function() {
      var analysis = new GenericObjectViewWithLabel();
      analysis.label = this.rectType_ + ' on layer ' + this.layer_.layerId;
      analysis.object = this.data_;
      return analysis;
    },

    get title() {
      return this.rectType_;
    },

    findEquivalent: function(lthi) {
      return undefined;
    }
  };

  /**
   * @constructor
   */
  function AnimationRectSelection(layer, rect) {
    this.layer_ = layer;
    this.rect_ = rect;
  }

  AnimationRectSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 0;
    },

    get associatedLayerId() {
      return this.layer_.layerId;
    },

    createAnalysis: function() {
      var analysis = new GenericObjectViewWithLabel();
      analysis.label = 'Animation Bounds of layer ' + this.layer_.layerId;
      analysis.object = this.rect_;
      return analysis;
    },

    get title() {
      return 'AnimationRectSelection';
    }
  };

  /**
   * @constructor
   */
  function RasterTaskSelection(rasterTask) {
    this.rasterTask_ = rasterTask;
  }

  RasterTaskSelection.prototype = {
    __proto__: Selection.prototype,

    get specicifity() {
      return 3;
    },

    get tile() {
      return this.rasterTask_.args.data.tile_id;
    },

    get associatedLayerId() {
      return this.tile.layerId;
    },

    get layerRect() {
      return this.tile.layerRect;
    },

    createAnalysis: function() {
      var sel = new tracing.Selection();
      sel.push(this.rasterTask_);
      var analysis = new tracing.analysis.AnalysisResults();
      tracing.analysis.analyzeSelection(analysis, sel);
      return analysis;
    },

    get title() {
      return this.rasterTask_.title;
    },

    findEquivalent: function(lthi) {
      // Raster tasks are only valid in one LTHI.
      return undefined;
    }
  };

  return {
    Selection: Selection,
    RenderPassSelection: RenderPassSelection,
    LayerSelection: LayerSelection,
    TileSelection: TileSelection,
    LayerRectSelection: LayerRectSelection,
    AnimationRectSelection: AnimationRectSelection,
    RasterTaskSelection: RasterTaskSelection
  };
});
