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

      this.image = undefined; // set externally.
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
      this.rasterData_.data = new Uint8ClampedArray(this.rasterData_.data);
      return this.rasterData_;
    },

    beginRenderingImage: function(imageReadyCallback) {
      var rd = this.getRasterData();
      var helperCanvas = document.createElement('canvas');
      helperCanvas.width = rd.width;
      helperCanvas.height = rd.height;
      var ctx = helperCanvas.getContext('2d');
      var imageData = ctx.createImageData(rd.width, rd.height);
      imageData.data.set(rd.data);
      ctx.putImageData(imageData, 0, 0);
      var img = document.createElement('img');
      img.onload = function() {
        this.image = img;
        imageReadyCallback();
      }.bind(this);
      img.src = helperCanvas.toDataURL();
    }
  };

  ObjectSnapshot.register('cc::Picture', PictureSnapshot);

  return {
    PictureSnapshot: PictureSnapshot
  };
});
