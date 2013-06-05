// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('cc.constants');
base.require('cc.region');
base.require('tracing.trace_model.object_instance');

base.exportTo('cc', function() {
  var constants = cc.constants;
  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  /**
   * @constructor
   */
  function LayerImplSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  LayerImplSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);

      this.layerTreeImpl_ = undefined;
      this.parentLayer = undefined;
    },

    initialize: function() {
      // Defaults.
      this.invalidation = new cc.Region();
      this.pictures = [];

      // Import & validate this.args
      cc.moveRequiredFieldsFromArgsToToplevel(
          this, ['layerId', 'children',
            'layerQuad']);
      cc.moveOptionalFieldsFromArgsToToplevel(
          this, ['maskLayer', 'replicaLayer']);

      // Leave bounds in both places.
      this.bounds = base.Rect.FromXYWH(
          0, 0,
          this.args.bounds.width, this.args.bounds.height);

      for (var i = 0; i < this.children.length; i++)
        this.children[i].parentLayer = this;
      if (this.maskLayer)
        this.maskLayer.parentLayer = this;
      if (this.replicaLayer)
        this.maskLayer.replicaLayer = this;
    },

    get layerTreeImpl() {
      if (this.layerTreeImpl_)
        return this.layerTreeImpl_;
      if (this.parentLayer)
        return this.parentLayer.layerTreeImpl;
      return undefined;
    },
    set layerTreeImpl(layerTreeImpl) {
      this.layerTreeImpl_ = layerTreeImpl;
    },

    get activeLayer() {
      if (this.layerTreeImpl.whichTree == constants.ACTIVE_TREE)
        return this;
      var activeTree = this.layerTreeImpl.layerTreeHostImpl.activeTree;
      return activeTree.findLayerWithId(this.layerId);
    },

    get pendingLayer() {
      if (this.layerTreeImpl.whichTree == constants.PENDING_TREE)
        return this;
      var pendingTree = this.layerTreeImpl.layerTreeHostImpl.pendingTree;
      return pendingTree.findLayerWithId(this.layerId);
    }
  };

  /**
   * @constructor
   */
  function PictureLayerImplSnapshot() {
    LayerImplSnapshot.apply(this, arguments);
  }

  PictureLayerImplSnapshot.prototype = {
    __proto__: LayerImplSnapshot.prototype,

    initialize: function() {
      LayerImplSnapshot.prototype.initialize.call(this);

      if (this.args.invalidation) {
        this.invalidation = cc.RegionFromArray(this.args.invalidation);
        delete this.args.invalidation;
      }
      if (this.args.pictures) {
        this.pictures = this.args.pictures;
      }
    }
  };

  ObjectSnapshot.register('cc::LayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::PictureLayerImpl', PictureLayerImplSnapshot);

  ObjectSnapshot.register('cc::DelegatedRendererLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::HeadsUpDisplayLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::IOSurfaceLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::NinePatchLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::PictureImageLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::ScrollbarLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::SolidColorLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::TextureLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::TiledLayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::VideoLayerImpl', LayerImplSnapshot);

  return {
    LayerImplSnapshot: LayerImplSnapshot,
    PictureLayerImplSnapshot: PictureLayerImplSnapshot
  };
});
