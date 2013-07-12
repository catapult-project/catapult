// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.analyze_selection');
base.require('tracing.analysis.analysis_results');

base.exportTo('cc', function() {
  var tsRound = tracing.analysis.tsRound;

  function Selection() {

  };
  Selection.prototype = {
    /**
     * If a selection is related to a specific layer, then this returns the
     * layerId of that layer. If the selection is not related to a layer, for
     * example if the device viewport is selected, then this returns undefined.
     */
    get associatedLayerId() {
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
     * Called when the selection is made active in the layer viewer. Must return
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
  function LayerSelection(layer) {
    if (!layer)
      throw new Error('Layer is required');
    this.layer_ = layer;
  }

  LayerSelection.prototype = {
    __proto__: Selection.prototype,

    get associatedLayerId() {
      return this.layer_.layerId;
    },

    get quadIfPending() {
      return undefined;
    },

    get quadIfActive() {
      return undefined;
    },

    createAnalysis: function() {
      var dataView = new tracing.analysis.GenericObjectView();
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

    get associatedLayerId() {
      return this.tile_.layerId;
    },

    get quadIfPending() {
      return this.tile_.args.pendingPriority.currentScreenQuad;
    },

    get quadIfActive() {
      return this.tile_.args.activePriority.currentScreenQuad;
    },

    createAnalysis: function() {
      var analysis = new tracing.analysis.GenericObjectView();
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
  function RasterTaskSelection(rasterTask) {
    this.rasterTask_ = rasterTask;
  }

  RasterTaskSelection.prototype = {
    __proto__: Selection.prototype,

    get tile() {
      return this.rasterTask_.args.data.tile_id;
    },

    get associatedLayerId() {
      return this.tile.layerId;
    },

    get quadIfPending() {
      return this.tile.args.pendingPriority.currentScreenQuad;
    },

    get quadIfActive() {
      return this.tile.args.activePriority.currentScreenQuad;
    },

    createAnalysis: function() {
      var sel = tracing.createSelectionFromObjectAndView(
          this.rasterTask_, this);
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
    LayerSelection: LayerSelection,
    TileSelection: TileSelection,
    RasterTaskSelection: RasterTaskSelection
  };
});
