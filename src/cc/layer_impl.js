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
      cc.moveFieldsFromArgsToToplevel(this);
      cc.assertHasField(this, 'children');
      cc.assertHasField(this, 'layerQuad');

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

  ObjectSnapshot.register('cc::LayerImpl', LayerImplSnapshot);

  // For now, handle PictureLayerImpl's using LayerImpl classes.
  ObjectSnapshot.register('cc::PictureLayerImpl', LayerImplSnapshot);

  return {
    LayerImplSnapshot: LayerImplSnapshot
  };
});
