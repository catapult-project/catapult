// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('tracing.trace_model.object_instance');
base.require('cc.util');

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
          this, ['layerId']);
    }
  };

  ObjectSnapshot.register('cc::Tile', TileSnapshot);

  return {
    TileSnapshot: TileSnapshot
  };
});
