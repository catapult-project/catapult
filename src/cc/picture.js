// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.raf');
base.require('base.rect');
base.require('tracing.trace_model.object_instance');
base.require('cc.util');

base.exportTo('cc', function() {

  var ObjectSnapshot = tracing.trace_model.ObjectSnapshot;

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
    var usualReason = [
      'For pictures to show up, you need to have Chrome running with ',
      '--enable-skia-benchmarking. Please restart chrome with this flag ',
      'and try again.'
    ].join('');

    if (!window.chrome)
      return usualReason;
    if (!window.chrome.skiaBenchmarking)
      return usualReason;
    if (!window.chrome.skiaBenchmarking.rasterize)
      return 'Your chrome is old';
    return 'Rasterizing is on';
  }

  var RASTER_IMPOSSIBLE = -2;
  var RASTER_FAILED = -1;
  var RASTER_NOT_BEGUN = 0;
  var RASTER_SUCCEEDED = 1;

  PictureSnapshot.prototype = {
    __proto__: ObjectSnapshot.prototype,

    preInitialize: function() {
      cc.preInitializeObject(this);

      if (PictureSnapshot.CanRasterize())
        this.rasterStatus_ = RASTER_NOT_BEGUN;
      else
        this.rasterStatus_ = RASTER_IMPOSSIBLE;
      this.rasterResult_ = undefined;

      this.image_ = undefined;
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

    rasterize_: function() {
      if (this.rasterStatus_ != RASTER_NOT_BEGUN)
        throw new Error('Rasterized already');

      if (!PictureSnapshot.CanRasterize()) {
        console.error(PictureSnapshot.HowToEnableRasterizing());
        return undefined;
      }

      var res = window.chrome.skiaBenchmarking.rasterize({
        skp64: this.args.skp64,
        params: {
          layer_rect: this.args.params.layerRect,
          opaque_rect: this.args.params.opaqueRect
        }
      });
      if (!res) {
        this.rasterStatus_ = RASTER_FAILED;
        return;
      }

      this.rasterStatus_ = RASTER_SUCCEEDED;
      this.rasterResult_ = {
        width: res.width,
        height: res.height,
        data: new Uint8ClampedArray(res.data)
      };
    },

    get image() {
      return this.image_;
    },

    get canRasterizeImage() {
      if (this.rasterStatus_ == RASTER_SUCCEEDED)
        return true;
      return this.rasterStatus_ == RASTER_NOT_BEGUN;
    },

    beginRasterizingImage: function(imageReadyCallback) {
      if (this.rasterStatus_ == RASTER_IMPOSSIBLE ||
          this.rasterStatus_ == RASTER_FAILED)
        throw new Error('Cannot render image');

      if (this.rasterStatus_ == RASTER_SUCCEEDED)
        throw new Error('Cannot render image');

      this.rasterize_();
      if (this.rasterStatus_ == RASTER_FAILED) {
        base.requestAnimationFrameInThisFrameIfPossible(imageReadyCallback);
        return;
      }
      var rd = this.rasterResult_;

      var helperCanvas = document.createElement('canvas');
      helperCanvas.width = rd.width;
      helperCanvas.height = rd.height;
      var ctx = helperCanvas.getContext('2d');
      var imageData = ctx.createImageData(rd.width, rd.height);
      imageData.data.set(rd.data);
      ctx.putImageData(imageData, 0, 0);
      var img = document.createElement('img');
      img.onload = function() {
        this.image_ = img;
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
