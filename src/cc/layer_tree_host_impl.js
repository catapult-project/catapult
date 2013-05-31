// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the LayerTreeHostImpl model-level objects.
 */
base.require('base.bbox2');
base.require('tracing.trace_model.object_instance');
base.require('cc.constants');
base.require('cc.layer_tree_impl');
base.require('cc.util');

base.exportTo('cc', function() {
  var constants = cc.constants;
  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;
  var ObjectInstance = tracing.trace_model.ObjectInstance;

  /**
   * @constructor
   */
  function LayerTreeHostImplSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  LayerTreeHostImplSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);
    },

    initialize: function() {
      cc.moveRequiredFieldsFromArgsToToplevel(
          this, ['deviceViewportSize',
            'activeTree']);
      cc.moveOptionalFieldsFromArgsToToplevel(
          this, ['pendingTree',
            'tiles']);

      this.activeTree.layerTreeHostImpl = this;
      this.activeTree.whichTree = constants.ACTIVE_TREE;
      if (this.pendingTree) {
        this.pendingTree.layerTreeHostImpl = this;
        this.pendingTree.whichTree = constants.PENDING_TREE;
      }
    },

    getTree: function(whichTree) {
      if (whichTree == constants.ACTIVE_TREE)
        return this.activeTree;
      if (whichTree == constants.PENDING_TREE)
        return this.pendingTree;
      throw new Exception('Unknown tree type + ' + whichTree);
    }
  };

  ObjectSnapshot.register('cc::LayerTreeHostImpl', LayerTreeHostImplSnapshot);

  /**
   * @constructor
   */
  function LayerTreeHostImplInstance() {
    ObjectInstance.apply(this, arguments);

    this.allLayersBBox_ = undefined;
  }

  LayerTreeHostImplInstance.prototype = {
    __proto__: ObjectInstance.prototype,

    get allContentsScales() {
      if (this.allContentsScales_)
        return this.allContentsScales_;

      var scales = {};
      for (var tileID in this.allTileHistories_) {
        var tileHistory = this.allTileHistories_[tileID];
        scales[tileHistory.contentsScale] = true;
      }
      this.allContentsScales_ = base.dictionaryKeys(scales);
      return this.allContentsScales_;
    },

    get allLayersBBox() {
      if (this.allLayersBBox_)
        return this.allLayersBBox_;
      var bbox = new base.BBox2();
      function handleTree(tree) {
        tree.renderSurfaceLayerList.forEach(function(layer) {
          bbox.addQuad(layer.layerQuad);
        });
      }
      this.snapshots.forEach(function(lthi) {
        handleTree(lthi.activeTree);
        if (lthi.pendingTree)
          handleTree(lthi.pendingTree);
      });
      this.allLayersBBox_ = bbox;
      return this.allLayersBBox_;
    }
  };

  ObjectInstance.register('cc::LayerTreeHostImpl', LayerTreeHostImplInstance);

  return {
    LayerTreeHostImplSnapshot: LayerTreeHostImplSnapshot,
    LayerTreeHostImplInstance: LayerTreeHostImplInstance

  };
});
