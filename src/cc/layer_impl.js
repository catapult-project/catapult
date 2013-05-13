// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

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
      // Import & validate this.args
      cc.moveRequiredFieldsFromArgsToToplevel(
        this, ['children',
               'layerQuad']);
      cc.moveOptionalFieldsFromArgsToToplevel(
        this, ['maskLayer', 'replicaLayer']);

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

  // For now, handle PictureLayerImpl's using LayerImpl classes.
  // Deprecated.
  ObjectSnapshot.register('cc::LayerImpl', LayerImplSnapshot);
  ObjectSnapshot.register('cc::PictureLayerImpl', LayerImplSnapshot);

  ObjectSnapshot.register('ContentLayer', LayerImplSnapshot);
  ObjectSnapshot.register('DelegatedRendererLayer', LayerImplSnapshot);
  ObjectSnapshot.register('HeadsUpDisplayLayer', LayerImplSnapshot);
  ObjectSnapshot.register('IOSurfaceLayer', LayerImplSnapshot);
  ObjectSnapshot.register('Layer', LayerImplSnapshot);
  ObjectSnapshot.register('NinePatchLayer', LayerImplSnapshot);
  ObjectSnapshot.register('PictureImageLayer', LayerImplSnapshot);
  ObjectSnapshot.register('PictureLayer', LayerImplSnapshot);
  ObjectSnapshot.register('ScrollbarLayer', LayerImplSnapshot);
  ObjectSnapshot.register('SolidColorLayer', LayerImplSnapshot);
  ObjectSnapshot.register('TextureLayer', LayerImplSnapshot);
  ObjectSnapshot.register('VideoLayer', LayerImplSnapshot);

  return {
    LayerImplSnapshot: LayerImplSnapshot
  };
});
