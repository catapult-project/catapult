// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.range');
base.require('base.events');

base.exportTo('ui', function() {
  // FIXME(pdr): Replace this padding with just what's necessary for
  //             drawing borders / highlights.
  //             https://code.google.com/p/trace-viewer/issues/detail?id=228
  var constants = {
    // The ratio of quad stack pixels to world pixels before CSS scaling.
    DEVICE_PIXELS_PER_WORLD_PIXEL: 1.0,
    // Extra area surrounding the quad bounding box to help
    // see border/highlights
    DEFAULT_PAD_PERCENTAGE: 0.00
  };

  function QuadViewViewport(worldRect,
                            opt_devicePixelsPerWorldPixel,
                            opt_padding,
                            opt_devicePixelRatio) {
    base.EventTarget.call(this);
    if (!worldRect)
      throw new Error('Cannot initialize a viewport with an empty worldRect');

    // Physical pixels / device-independent pixels;
    // 1 is normal; higher for eg Retina
    this.devicePixelsPerLayoutPixel_ =
        opt_devicePixelRatio || window.devicePixelRatio || 1;

    this.layoutRect_ = undefined;
    this.setWorldRect_(worldRect, opt_padding);

    this.updateScale_(opt_devicePixelsPerWorldPixel ||
        constants.DEVICE_PIXELS_PER_WORLD_PIXEL);
  }

  QuadViewViewport.prototype = {

    __proto__: base.EventTarget.prototype,

    get layoutPixelsPerWorldPixel() {
      return this.layoutPixelsPerWorldPixel_;
    },

    get devicePixelsPerLayoutPixel() {
      return this.devicePixelsPerLayoutPixel_;
    },

    // The browsers internal coordinate limits, padded, no scaling.
    get worldRect() {
      return this.worldRect_;
    },

    // The browsers original internal coodinate limits.
    get unpaddedWorldRect() {
      return this.unpaddedWorldRect_;
    },

    // Our DOM representation of the coordinate limits.
    // A DOM element with this w x h will enclose the
    // the world as represented by our canvases.
    get layoutRect() {
      return this.layoutRect_;
    },

    get transformDevicePixelsToWorld() {
      return this.transformDevicePixelsToWorld_;
    },

    get transformWorldToDevicePixels() {
      return this.transformWorldToDevicePixels_;
    },

    get devicePixelsPerWorldPixel() {
      return this.devicePixelsPerWorldPixel_;
    },

    set devicePixelsPerWorldPixel(newValue) {
      this.updateScale_(newValue);
    },

    updateBoxSize: function(canvas) {
      // http://www.html5rocks.com/en/tutorials/canvas/hidpi/
      // The |ratio| in the above article is our devicePixelsPerLayoutPixel
      //
      var resizedCanvas = false;
      if (canvas.width !== this.worldWidthInDevicePixels_) {
        canvas.width = this.worldWidthInDevicePixels_ * ui.RASTER_SCALE;
        canvas.style.width = this.layoutRect_.width + 'px';
        resizedCanvas = true;
      }
      if (canvas.height !== this.worldHeightInDevicePixels_) {
        canvas.height = this.worldHeightInDevicePixels_ * ui.RASTER_SCALE;
        canvas.style.height = this.layoutRect_.height + 'px';
        resizedCanvas = true;
      }
      return resizedCanvas;
    },

    layoutPixelsToWorldPixels: function(v) {
      var tmp = this.layoutPixelsToDevicePixels(v);
      return this.devicePixelsToWorldPixels(tmp);
    },

    layoutPixelsToDevicePixels: function(v) {
      var res = vec2.create();
      return vec2.scale(res, v, this.devicePixelsPerLayoutPixel_);
    },

    devicePixelsToWorldPixels: function(v) {
      var res = vec2.create();
      vec2.transformMat2d(res, v, this.transformDevicePixelsToWorld_);
      return res;
    },

    worldPixelsToLayoutPixels: function(v) {
      var devicePixels = vec2.create();
      vec2.transformMat2d(devicePixels, v,
          this.transformWorldToDevicePixels_);
      var res = vec2.create();
      return vec2.scale(res, devicePixels,
          1 / this.devicePixelsPerLayoutPixel_);
    },

    getWorldToDevicePixelsTransform: function() {
      return this.transformWorldToDevicePixels_;
    },

    getDeviceLineWidthAssumingTransformIsApplied: function(
        desiredDeviceLineWidth) {
      return desiredDeviceLineWidth / this.devicePixelsPerWorldPixel_;
    },

    applyTransformToContext: function(ctx) {
      var transform = this.transformWorldToDevicePixels_;
      ctx.transform(transform[0], transform[1], transform[2],
                    transform[3], transform[4], transform[5]);
    },

    forceRedrawAll: function() {
      this.didChange_();
    },

    //-------------------------------------------

    updateScale_: function(newValue) {
      this.devicePixelsPerWorldPixel_ = newValue;

      this.layoutPixelsPerWorldPixel_ = this.devicePixelsPerWorldPixel_ /
          this.devicePixelsPerLayoutPixel_;


      this.worldWidthInDevicePixels_ =
          this.worldRect_.width * this.devicePixelsPerWorldPixel_;
      this.worldHeightInDevicePixels_ =
          this.worldRect_.height * this.devicePixelsPerWorldPixel_;

      this.updateLayoutRect_();

      this.transformWorldToDevicePixels_ = mat2d.create();
      this.transformDevicePixelsToWorld_ = mat2d.create();
      this.updateTransform_();
    },

    /** Adjust the scaled world box for Retina-like displays */
    updateLayoutRect_: function() {
      var devicePixelsPerLayoutPixel =
          this.devicePixelsPerWorldPixel_ / this.devicePixelsPerLayoutPixel_;
      this.layoutRect_ = this.worldRect.scale(devicePixelsPerLayoutPixel);
    },

    setWorldRect_: function(worldRect, opt_padding) {
      var worldPad;
      var padding;
      if (opt_padding !== undefined) {
        padding = opt_padding;
      } else {
        padding = constants.DEFAULT_PAD_PERCENTAGE;
      }
      worldPad = Math.min(worldRect.width,
                          worldRect.height) * padding;

      this.unpaddedWorldRect_ = worldRect;
      this.worldRect_ = worldRect.clone().enlarge(worldPad);
    },

    updateTransform_: function() {
      if (!this.transformWorldToDevicePixels_)
        return;

      mat2d.identity(this.transformWorldToDevicePixels_);
      mat2d.translateXY(
          this.transformWorldToDevicePixels_,
          -this.worldRect_.x, -this.worldRect_.y);
      mat2d.scaleXY(this.transformWorldToDevicePixels_,
          this.devicePixelsPerWorldPixel_,
          this.devicePixelsPerWorldPixel_);

      mat2d.invert(this.transformDevicePixelsToWorld_,
                   this.transformWorldToDevicePixels_);
      this.didChange_();
    },

    didChange_: function() {
      base.dispatchSimpleEvent(this, 'change', false, false);
    }
  };

  return {
    QuadViewViewport: QuadViewViewport
  };
});
