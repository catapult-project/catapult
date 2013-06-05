// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.object_instance');
base.require('cc.layer_impl');

base.exportTo('cc', function() {
  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  /**
   * @constructor
   */
  function LayerTreeImplSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  LayerTreeImplSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);
      this.layerTreeHostImpl = undefined;
      this.whichTree = undefined;
    },

    initialize: function() {
      cc.moveRequiredFieldsFromArgsToToplevel(
          this, ['rootLayer',
            'renderSurfaceLayerList']);
      this.rootLayer.layerTreeImpl = this;
    },

    iterLayers: function(func) {
      function visitLayer(layer, depth, isMask, isReplica) {
        func(layer, depth, isMask, isReplica);
        for (var i = 0; i < layer.children.length; i++)
          visitLayer(layer.children[i], depth + 1);
        if (layer.maskLayer)
          visitLayer(layer, depth + 1, true, false);
        if (layer.replicaLayer)
          visitLayer(layer, depth + 1, false, true);
      }
      visitLayer(this.rootLayer, 0, false, false);
    },
    findLayerWithId: function(id) {
      var foundLayer = undefined;
      function visitLayer(layer) {
        if (layer.layerId == id)
          foundLayer = layer;
      }
      this.iterLayers(visitLayer);
      return foundLayer;
    }
  };

  ObjectSnapshot.register('cc::LayerTreeImpl', LayerTreeImplSnapshot);

  return {
    LayerTreeImplSnapshot: LayerTreeImplSnapshot
  };
});
