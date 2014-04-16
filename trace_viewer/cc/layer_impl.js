// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.rect');
tvcm.require('cc.constants');
tvcm.require('cc.region');
tvcm.require('cc.tile_coverage_rect');
tvcm.require('tracing.trace_model.object_instance');

tvcm.exportTo('cc', function() {
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
      this.unrecordedRegion = new cc.Region();
      this.pictures = [];

      // Import & validate this.args
      cc.moveRequiredFieldsFromArgsToToplevel(
          this, ['layerId', 'children',
                 'layerQuad']);
      cc.moveOptionalFieldsFromArgsToToplevel(
          this, ['maskLayer', 'replicaLayer',
                 'idealContentsScale', 'geometryContentsScale',
                 'layoutRects', 'usingGpuRasterization']);

      // Leave bounds in both places.
      this.bounds = tvcm.Rect.fromXYWH(
          0, 0,
          this.args.bounds.width, this.args.bounds.height);

      if (this.args.animationBounds) {
        // AnimationBounds[2] and [5] are the Z-component of the box.
        this.animationBoundsRect = tvcm.Rect.fromXYWH(
            this.args.animationBounds[0], this.args.animationBounds[1],
            this.args.animationBounds[3], this.args.animationBounds[4]);
      }

      for (var i = 0; i < this.children.length; i++)
        this.children[i].parentLayer = this;
      if (this.maskLayer)
        this.maskLayer.parentLayer = this;
      if (this.replicaLayer)
        this.maskLayer.replicaLayer = this;
      if (!this.geometryContentsScale)
        this.geometryContentsScale = 1.0;

      this.touchEventHandlerRegion = cc.Region.fromArrayOrUndefined(
          this.args.touchEventHandlerRegion);
      this.wheelEventHandlerRegion = cc.Region.fromArrayOrUndefined(
          this.args.wheelEventHandlerRegion);
      this.nonFastScrollableRegion = cc.Region.fromArrayOrUndefined(
          this.args.nonFastScrollableRegion);
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
        this.invalidation = cc.Region.fromArray(this.args.invalidation);
        delete this.args.invalidation;
      }
      if (this.args.unrecordedRegion) {
        this.unrecordedRegion = cc.Region.fromArray(
            this.args.unrecordedRegion);
        delete this.args.unrecordedRegion;
      }
      if (this.args.pictures) {
        this.pictures = this.args.pictures;

        // The picture list comes in with an unknown ordering. We resort based
        // on timestamp order so we will draw the base picture first and the
        // various fixes on top of that.
        this.pictures.sort(function(a, b) { return a.ts - b.ts; });
      }

      this.tileCoverageRects = [];
      if (this.args.coverageTiles) {
        for (var i = 0; i < this.args.coverageTiles.length; ++i) {
          var rect = this.args.coverageTiles[i].geometryRect;
          var tile = this.args.coverageTiles[i].tile;
          this.tileCoverageRects.push(new cc.TileCoverageRect(rect, tile));
        }
        delete this.args.coverageTiles;
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
  ObjectSnapshot.register('cc::PaintedScrollbarLayerImpl', LayerImplSnapshot);

  ObjectSnapshot.register('ClankPatchLayer', LayerImplSnapshot);
  ObjectSnapshot.register('TabBorderLayer', LayerImplSnapshot);
  ObjectSnapshot.register('CounterLayer', LayerImplSnapshot);

  return {
    LayerImplSnapshot: LayerImplSnapshot,
    PictureLayerImplSnapshot: PictureLayerImplSnapshot
  };
});
