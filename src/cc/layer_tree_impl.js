// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.model.object_instance');
base.require('cc.layer_impl');

base.exportTo('cc', function() {
  var ObjectSnapshot = tracing.model.ObjectSnapshot;

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
    }
  };

  ObjectSnapshot.register('cc::LayerTreeImpl', LayerTreeImplSnapshot);

  return {
    LayerTreeImplSnapshot: LayerTreeImplSnapshot
  };
});
