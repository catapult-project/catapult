// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.range');
base.require('base.event_target');

base.exportTo('ui', function() {
  var DEFAULT_PAD_PERCENTAGE = 0.75;

  function QuadViewViewport(bbox,
                            opt_scale,
                            opt_deviceViewport,
                            opt_padding,
                            opt_devicePixelRatio) {
    base.EventTarget.call(this);
    if (bbox.isEmpty)
      throw new Error('Cannot initialize a viewport with an empty bbox');

    this.layoutRect = undefined;
    this.setWorldBBox(bbox, opt_padding);

    var devicePixelRatio;
    if (opt_devicePixelRatio)
      this.devicePixelRatio = opt_devicePixelRatio;
    else
      this.devicePixelRatio = window.devicePixelRatio || 1;

    var scale;
    if (opt_scale) {
      scale = opt_scale;
    } else {
      if (this.devicePixelRatio > 1)
        scale = 0.25;
      else
        scale = 0.125;
    }
    this.scale_ = scale;

    this.deviceViewport_ = opt_deviceViewport;

    this.updateScale_();
  }

  QuadViewViewport.prototype = {

    __proto__: base.EventTarget.prototype,

    set scale(scale) {
      this.scale_ = scale;
      this.updateScale_();
      this.didChange_();
    },

    get scale() {
      return this.scale_;
    },

    // The area of the world that is visible by users, in world pixels
    get deviceViewport() {
      return this.deviceViewport_;
    },

    updateScale_: function() {
      this.worldPixelsPerDevicePixel_ = this.scale_;
      this.devicePixelsPerLayoutPixel_ = 1 / this.devicePixelRatio;

      this.deviceWidth =
          this.worldRect.width * this.worldPixelsPerDevicePixel_;
      this.deviceHeight =
          this.worldRect.height * this.worldPixelsPerDevicePixel_;

      this.layoutRect = base.Rect.FromXYWH(
          this.worldRect.x * this.devicePixelsPerLayoutPixel_,
          this.worldRect.y * this.devicePixelsPerLayoutPixel_,
          this.deviceWidth * this.devicePixelsPerLayoutPixel_,
          this.deviceHeight * this.devicePixelsPerLayoutPixel_);
      this.effectiveWorldRect = this.worldRect.clone().scale(this.scale_);

      this.transformWorldToDevicePixels_ = mat2d.create();
      this.transformDevicePixelsToWorld_ = mat2d.create();
      this.updateTransform_();
    },

    setWorldBBox: function(bbox, opt_padding) {
      var worldRect = bbox.asRect();
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
      this.updateScale_();
      this.updateTransform_();
      this.didChange_();
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

    layoutPixelsToWorldPixels2: function(v) {
      var tmp = this.layoutPixelsToDevicePixels2(v);
      return this.devicePixelsToWorldPixels2(tmp);
    },

    layoutPixelsToDevicePixels2: function(v) {
      var res = vec2.create();
      return vec2.scale(res, v, 1 / this.devicePixelsPerLayoutPixel_);
    },

    devicePixelsToWorldPixels2: function(v) {
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

    didChange_: function() {
      base.dispatchSimpleEvent(this, 'change', false, false);
    }
  };

  return {
    QuadViewViewport: QuadViewViewport
  };
});
