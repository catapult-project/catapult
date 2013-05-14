// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc.region');
base.require('tracing.model.object_instance');

base.exportTo('cc', function() {
  var ObjectSnapshot = tracing.model.ObjectSnapshot;

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
        this, ['children',
               'layerQuad']);
      cc.moveOptionalFieldsFromArgsToToplevel(
        this, ['maskLayer', 'replicaLayer']);

      // Leave bounds in both places.
      this.bounds = this.args.bounds;

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
        delete this.args.pictures;
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
