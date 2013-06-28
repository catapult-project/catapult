// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.range');
base.require('base.event_target');

base.exportTo('ui', function() {
  var DEFAULT_PAD_PERCENTAGE = 0.75;

  function QuadViewViewport(worldRect,
                            opt_quad_stack_scale,
                            opt_deviceViewportRect,
                            opt_padding,
                            opt_devicePixelRatio) {
    base.EventTarget.call(this);
    if (!worldRect)
      throw new Error('Cannot initialize a viewport with an empty worldRect');

    this.layoutRect_ = undefined;
    this.setWorldRect_(worldRect, opt_padding);

    // Physical pixels / device-independent pixels;
    // 1 is normal; higher for eg Retina
    var devicePixelRatio;
    if (opt_devicePixelRatio)
      this.devicePixelRatio = opt_devicePixelRatio;
    else
      this.devicePixelRatio = window.devicePixelRatio || 1;

    var scale;
    if (opt_quad_stack_scale) {
      scale = opt_quad_stack_scale;
    } else {
      scale = 0.125;
      if (this.devicePixelRatio > 1)
        scale = scale * this.devicePixelRatio;
    }
    this.worldPixelsPerDevicePixel_ = scale;

    if (opt_deviceViewportRect) {
      this.deviceViewportRect_ = new base.Rect.FromXYWH(
          opt_deviceViewportRect.x || 0,
          opt_deviceViewportRect.y || 0,
          opt_deviceViewportRect.width || 0,
          opt_deviceViewportRect.height || 0);
    }

    this.updateScale_();
  }

  QuadViewViewport.prototype = {

    __proto__: base.EventTarget.prototype,

    // The pixels in the original, traced browser are
    // represented in a canvas 'world', scaled by a
    // this 'scale' value.
    set scale(scale) {
      this.worldPixelsPerDevicePixel_ = scale;
      this.updateScale_();
      this.didChange_();
    },

    get scale() {
      return this.worldPixelsPerDevicePixel_;
    },

    // The part of the world that is visible by users, in world pixels.
    // Maybe undefined.
    get deviceViewportRect() {
      return this.deviceViewportRect_;
    },

    updateBoxSize: function(canvas) {
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
      return vec2.scale(res, v, this.devicePixelRatio);
    },

    devicePixelsToWorldPixels: function(v) {
      var res = vec2.create();
      vec2.transformMat2d(res, v, this.transformDevicePixelsToWorld_);
      return res;
    },

    getWorldToDevicePixelTransform: function() {
      return this.transformDevicePixelsToWorld_;
    },

    getDeviceLineWidthAssumingTransformIsApplied: function(
        desiredDeviceLineWidth) {
      return desiredDeviceLineWidth / this.worldPixelsPerDevicePixel_;
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

    updateScale_: function() {
      // Scale the world to the size selected by the user.
      this.worldWidthInDevicePixels_ =
          this.worldRect.width * this.worldPixelsPerDevicePixel_;
      this.worldHeightInDevicePixels_ =
          this.worldRect.height * this.worldPixelsPerDevicePixel_;

      this.updateLayoutRect_();

      this.transformWorldToDevicePixels_ = mat2d.create();
      this.transformDevicePixelsToWorld_ = mat2d.create();
      this.updateTransform_();
    },

    /** Adjust the scaled world box for Retina-like displays */
    updateLayoutRect_: function() {
      var devicePixelsPerLayoutPixel = 1 / this.devicePixelRatio;
      this.layoutRect_ = base.Rect.FromXYWH(
          this.worldRect.x * devicePixelsPerLayoutPixel,
          this.worldRect.y * devicePixelsPerLayoutPixel,
          this.worldWidthInDevicePixels_ * devicePixelsPerLayoutPixel,
          this.worldHeightInDevicePixels_ * devicePixelsPerLayoutPixel);
    },

    setWorldRect_: function(worldRect, opt_padding) {
      var worldPad;
      var padding;
      if (opt_padding !== undefined) {
        padding = opt_padding;
      } else {
        padding = DEFAULT_PAD_PERCENTAGE;
      }
      worldPad = Math.min(worldRect.width,
                          worldRect.height) * padding;

      worldRect = worldRect.enlarge(worldPad);
      this.worldRect = worldRect;
    },

    updateTransform_: function() {
      if (!this.transformWorldToDevicePixels_)
        return;

      mat2d.identity(this.transformWorldToDevicePixels_);
      mat2d.translateXY(
          this.transformWorldToDevicePixels_,
          -this.worldRect.x, -this.worldRect.y);
      mat2d.scaleXY(this.transformWorldToDevicePixels_,
          this.worldPixelsPerDevicePixel_,
          this.worldPixelsPerDevicePixel_);

      mat2d.invert(this.transformDevicePixelsToWorld_,
                   this.transformWorldToDevicePixels_);
    },

    didChange_: function() {
      base.dispatchSimpleEvent(this, 'change', false, false);
    }
  };

  return {
    QuadViewViewport: QuadViewViewport
  };
});
