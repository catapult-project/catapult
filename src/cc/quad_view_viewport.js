/* Copyright (c) 2012 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
'use strict';

base.require('base.range');
base.require('base.event_target');

base.exportTo('cc', function() {
  function QuadViewViewport(bbox,
                            opt_scale,
                            opt_dontPadBbox, opt_devicePixelRatio) {
    base.EventTarget.call(this);
    if (bbox.isEmpty)
      throw new Error('Cannot initialize a viewport with an empty bbox');

    this.setWorldBBox(bbox, opt_dontPadBbox);

    var devicePixelRatio;
    if (opt_devicePixelRatio)
      devicePixelRatio = opt_devicePixelRatio;
    else
      devicePixelRatio = window.devicePixelRatio || 1;

    var scale;
    if (opt_scale) {
      scale = opt_scale;
    } else {
      if (devicePixelRatio > 1)
        scale = 0.25;
      else
        scale = 0.125;
    }
    this.scale_ = scale;
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

    updateScale_: function() {
      this.worldPixelsPerDevicePixel_ = this.scale_;
      this.devicePixelsPerLayoutPixel_ = 1 / devicePixelRatio;

      this.deviceWidth =
        this.worldRect.width * this.worldPixelsPerDevicePixel_;
      this.deviceHeight =
        this.worldRect.height * this.worldPixelsPerDevicePixel_;

      this.layoutWidth = this.deviceWidth * this.devicePixelsPerLayoutPixel_;
      this.layoutHeight = this.deviceHeight * this.devicePixelsPerLayoutPixel_;

      this.transformWorldToDevicePixels_ = mat2d.create();
      this.transformDevicePixelsToWorld_ = mat2d.create();
      this.updateTransform_();
    },

    setWorldBBox: function(bbox, opt_dontPadBbox) {
      var world_rect = bbox.asRect();
      var world_pad;
      if (opt_dontPadBbox) {
        world_pad = 0;
      } else {
        world_pad = Math.min(world_rect.width,
                             world_rect.height) * 0.10;
      }

      world_rect.enlarge(world_pad);
      this.worldRect = world_rect;
      this.updateScale_();
      this.updateTransform_();
      this.didChange_();
    },

    updateTransform_: function() {
      if (!this.transformWorldToDevicePixels_)
        return;

      mat2d.identity(this.transformWorldToDevicePixels_);
      mat2d.translateInplaceXY(
        this.transformWorldToDevicePixels_,
          -this.worldRect.left, -this.worldRect.top);
      mat2d.scaleInplaceXY(this.transformWorldToDevicePixels_,
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
        desired_device_line_width) {
      return desired_device_line_width / this.worldPixelsPerDevicePixel_;
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
    QuadViewViewport: QuadViewViewport,
  }
});

