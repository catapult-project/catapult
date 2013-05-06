// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Provides the LayerTreeHostImpl model-level objects.
 */
base.require('tracing.model.object_instance');
base.require('cc.layer_tree_impl');
base.require('cc.util');

base.exportTo('cc', function() {
  var ObjectSnapshot = tracing.model.ObjectSnapshot;
  var ObjectInstance = tracing.model.ObjectInstance;

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
      cc.moveFieldsFromArgsToToplevel(this);

      cc.assertHasField(this, 'deviceViewportSize');
      cc.assertHasField(this, 'activeTree');
    }
  };

  ObjectSnapshot.register('cc::LayerTreeHostImpl', LayerTreeHostImplSnapshot);

  /**
   * @constructor
   */
  function LayerTreeHostImplInstance() {
    ObjectInstance.apply(this, arguments);

    this.allContentsScales_ = undefined;
    this.allTilesBBox_ = undefined;
  }

  LayerTreeHostImplInstance.prototype = {
    __proto__: ObjectInstance.prototype,

    get allTileInstances() {
      /** */
    },

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

    get allTilesBBox() {
      if (this.allTilesBBox_)
        return this.allTilesBBox_;
      var bbox = new base.BBox2();
      this.allTilesBBox_ = bbox;
    },
  };

  ObjectInstance.register('cc::LayerTreeHostImpl', LayerTreeHostImplInstance);

  return {
    LayerTreeHostImplSnapshot: LayerTreeHostImplSnapshot,
    LayerTreeHostImplInstance: LayerTreeHostImplInstance

  }
});
