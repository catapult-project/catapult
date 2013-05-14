// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect2');
base.require('tracing.model.object_instance');

base.exportTo('', function() {

    var ObjectSnapshot = tracing.model.ObjectSnapshot;

  /**
   * @constructor
   */
  function PictureSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  PictureSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);
    },

    initialize: function() {
      cc.moveRequiredFieldsFromArgsToToplevel(
        this, ['layerRect',
               'dataB64']);
      this.layerRect = base.Rect2.FromArray(this.layerRect);
    }
  };

  ObjectSnapshot.register('cc::Picture', PictureSnapshot);

  return {
    PictureSnapshot: PictureSnapshot
  };
});
