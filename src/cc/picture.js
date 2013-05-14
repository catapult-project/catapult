// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect2');
base.require('tracing.model.object_instance');

base.exportTo('cc', function() {

  var ObjectSnapshot = tracing.model.ObjectSnapshot;

  /**
   * @constructor
   */
  function PictureSnapshot() {
    ObjectSnapshot.apply(this, arguments);
  }

  PictureSnapshot.CanRasterize = function() {
    if (!window.chrome)
      return false;
    if (!window.chrome.skiaBenchmarking)
      return false;
    if (!window.chrome.skiaBenchmarking.rasterize)
      return false;
    return true;
  }
  PictureSnapshot.HowToEnableRasterizing = function() {
    if (!window.chrome)
      return 'Please restart chrome with --enable-skia-benchmarking';
    if (!window.chrome.skiaBenchmarking)
      return 'Please restart chrome with --enable-skia-benchmarking';
    if (!window.chrome.skiaBenchmarking.rasterize)
      return 'Your chrome is old';
    return 'Rasterizing is on';
  }

  PictureSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);

      this.rasterData_ = undefined;
    },

    initialize: function() {
      cc.moveRequiredFieldsFromArgsToToplevel(
        this, ['layerRect',
               'dataB64']);
      this.layerRect = base.Rect2.FromArray(this.layerRect);
    },

    getRasterData: function() {
      if (this.rasterData_)
        return this.rasterData_;
      if (!PictureSnapshot.CanRasterize())
        return;
      this.rasterData_ = window.chrome.skiaBenchmarking.rasterize(this.dataB64);

      // Switch it to a Uint8ClampedArray.
      this.rasterData_.data = new Uint8ClampedArray (this.rasterData_.data);
      var d = this.rasterData_.data;
      for (var i = 0; i < d.length; i+= 4) {
        var x = d[i];
        d[i] = d[i+2];
        d[i+2] = x;
      }
      return this.rasterData_;
    }
  };

  ObjectSnapshot.register('cc::Picture', PictureSnapshot);

  return {
    PictureSnapshot: PictureSnapshot
  };
});
