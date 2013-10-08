// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('tracing.trace_model.object_instance');
base.require('cc.util');
base.require('cc.debug_colors');

base.exportTo('cc', function() {

  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

  /**
   * @constructor
   */
  function TileSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  TileSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);
    },

    initialize: function() {
      cc.moveOptionalFieldsFromArgsToToplevel(
          this, ['layerId', 'contentsScale', 'contentRect']);
      if (this.args.managedState) {
        this.resolution = this.args.managedState.resolution;
        this.isSolidColor = this.args.managedState.isSolidColor;
        this.isUsingGpuMemory = this.args.managedState.isUsingGpuMemory;
        this.hasResource = this.args.managedState.hasResource;
        this.scheduledPriority = this.args.managedState.scheduledPriority;
        this.distanceToVisible =
            this.args.managedState.distanceToVisibleInPixels;
        this.timeToVisible = this.args.managedState.timeToNeededInSeconds;
      } else {
        this.resolution = 'HIGH_RESOLUTION';
        this.isSolidColor = false;
        this.isUsingGpuMemory = false;
        this.hasResource = false;
        this.scheduledPriority = undefined;
        this.distanceToVisible = undefined;
        this.timeToVisible = undefined;
      }
      if (this.timeToVisible > 60)
        this.timeToVisible = 60;

      // This check is for backward compatability. It can probably
      // be removed once we're confident that most traces contain
      // content_rect.
      if (this.contentRect)
        this.layerRect = this.contentRect.scale(1.0 / this.contentsScale);

      if (this.isSolidColor)
        this.type_ = cc.tileTypes.solidColor;
      else if (!this.hasResource)
        this.type_ = cc.tileTypes.missing;
      else if (this.resolution === 'HIGH_RESOLUTION')
        this.type_ = cc.tileTypes.highRes;
      else if (this.resolution === 'LOW_RESOLUTION')
        this.type_ = cc.tileTypes.lowRes;
      else
        this.type_ = cc.tileTypes.unknown;
    },

    getTypeForLayer: function(layer) {
      var type = this.type_;
      if (type == cc.tileTypes.unknown) {
        if (this.contentsScale < layer.idealContentsScale)
          type = cc.tileTypes.extraLowRes;
        else if (this.contentsScale > layer.idealContentsScale)
          type = cc.tileTypes.extraHighRes;
      }
      return type;
    }
  };

  ObjectSnapshot.register('cc::Tile', TileSnapshot);

  return {
    TileSnapshot: TileSnapshot
  };
});
