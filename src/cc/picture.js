// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');
base.require('tracing.model.object_instance');
base.require('cc.util');

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
      if (!this.args.params.layerRect)
        throw new Error('Missing layer rect');
      this.layerRect = this.args.params.layerRect;
      this.layerRect = base.Rect.FromArray(this.layerRect);
    },

    getBase64SkpData: function() {
      return this.args.skp64;
    },

    getRasterData: function() {
      if (this.rasterData_)
        return this.rasterData_;

      if (!PictureSnapshot.CanRasterize()) {
        console.error(PictureSnapshot.HowToEnableRasterizing());
        return undefined;
      }

      this.rasterData_ = window.chrome.skiaBenchmarking.rasterize({
        skp64: this.args.skp64,
        params: {
          layer_rect: this.args.params.layerRect,
          opaque_rect: this.args.params.opaqueRect
        }
      });
      if (this.rasterData_) {
        // Switch it to a Uint8ClampedArray.
        this.rasterData_.data = new Uint8ClampedArray(this.rasterData_.data);
      }
      return this.rasterData_;
    },

    beginRenderingImage: function(imageReadyCallback) {
      var rd = this.getRasterData();
      if (!rd)
        return;

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
