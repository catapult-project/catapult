// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('ui');

base.exportTo('ui', function() {

  var constants = {
    DEFAULT_SCALE: 0.5,
    MINIMUM_SCALE: 0.1,
    MAXIMUM_SCALE: 2.0,
    RESCALE_TIMEOUT_MS: 200,
    MAXIMUM_TILT: 90, // degrees
  };


  var Camera = ui.define('camera');

  Camera.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function(eventSource) {
      this.eventSource_ = eventSource;

      this.eventSource_.addEventListener('beginpan',
          this.onPanBegin_.bind(this));
      this.eventSource_.addEventListener('updatepan',
          this.onPanUpdate_.bind(this));
      this.eventSource_.addEventListener('endpan',
          this.onPanEnd_.bind(this));

      this.eventSource_.addEventListener('beginzoom',
          this.onZoomBegin_.bind(this));
      this.eventSource_.addEventListener('updatezoom',
          this.onZoomUpdate_.bind(this));
      this.eventSource_.addEventListener('endzoom',
          this.onZoomEnd_.bind(this));

      // TODO(vmpstr): Change this to listen to rotate events
      // once those are in.
      this.eventSource_.addEventListener('begintiming',
          this.onRotateBegin_.bind(this));
      this.eventSource_.addEventListener('updatetiming',
          this.onRotateUpdate_.bind(this));
      this.eventSource_.addEventListener('endtiming',
          this.onRotateEnd_.bind(this));

      this.listeners_ = {};

      this.eye_ = [0, 0, -500];
      this.scale_ = constants.DEFAULT_SCALE;
      this.rotation_ = [0, 0];

      this.pixelRatio_ = window.devicePixelRatio || 1;
    },


    get modelViewMatrix() {
      var viewportRect_ =
          base.windowRectForElement(this.canvas_).scaleSize(this.pixelRatio_);
      var mvMatrix = mat4.create();

      // Translate modelView by the eye.
      mat4.translate(mvMatrix, mvMatrix, this.eye_);

      // Figure out around which point to rotate (considering scale).
      var x = (this.deviceRect_.left + this.deviceRect_.right) / 2;
      var y = (this.deviceRect_.top + this.deviceRect_.bottom) / 2;
      var p = [x * this.scale_, y * this.scale_, 0, 1];

      // Compute the rotation matrix.
      var rotation = mat4.create();
      mat4.rotate(rotation, rotation, this.rotation_[0], [1, 0, 0]);
      mat4.rotate(rotation, rotation, this.rotation_[1], [0, 1, 0]);

      // See where the original p is taken by the rotation matrix.
      var newP = [0, 0, 0];
      vec4.transformMat4(newP, p, rotation);

      // Figure out where to translate so that the rotation point stays
      // stationary.
      var delta = [p[0] - newP[0], p[1] - newP[1]];

      // Apply the translation.
      mat4.translate(mvMatrix, mvMatrix, [delta[0], delta[1], 0]);

      // Finally apply the rotation matrix itself.
      mat4.multiply(mvMatrix, mvMatrix, rotation);

      // Apply scale.
      mat4.scale(mvMatrix, mvMatrix, [this.scale_, this.scale_, 1]);

      return mvMatrix;
    },

    get projectionMatrix() {
      // TODO(vmpstr): Figure out perspective projection.
      var rect =
          base.windowRectForElement(this.canvas_).scaleSize(this.pixelRatio_);
      var matrix = mat4.create();
      mat4.ortho(matrix, 0, rect.width, 0, rect.height, 1, 1000);

      // NDC to viewport transform.
      mat4.translate(matrix, matrix, [1, 1, 0]);
      mat4.scale(matrix, matrix, [rect.width / 2, rect.height / 2, 1]);
      return matrix;
    },

    get scale() {
      return this.scale_;
    },

    set canvas(c) {
      this.canvas_ = c;
    },

    set deviceRect(rect) {
      this.deviceRect_ = rect;
    },

    resetCamera: function() {
      this.eye_ = [0, 0, -500];
      this.scale_ = constants.DEFAULT_SCALE;
      this.rotation_ = [0, 0];

      if (this.deviceRect_) {
        var rect =
            base.windowRectForElement(this.canvas_).scaleSize(this.pixelRatio_);
        this.scale_ = 0.7 * Math.min(rect.width / this.deviceRect_.width,
                                     rect.height / this.deviceRect_.height);
        this.scale_ = base.clamp(
            this.scale_, constants.MINIMUM_SCALE, constants.MAXIMUM_SCALE);
        this.eye_[0] +=
            (rect.width / 2) -
            this.scale_ * (this.deviceRect_.left + this.deviceRect_.right) / 2;
        this.eye_[1] +=
            (rect.height / 2) -
            this.scale_ * (this.deviceRect_.top + this.deviceRect_.bottom) / 2;
      }

      this.dispatchRenderEvent_();
    },

    updatePanByDelta: function(delta) {
      var rect =
          base.windowRectForElement(this.canvas_).scaleSize(this.pixelRatio_);

      this.eye_[0] += delta[0];
      this.eye_[1] += delta[1];

      var xLimits = [-this.deviceRect_.width * this.scale_, rect.width];
      var yLimits = [-this.deviceRect_.height * this.scale_, rect.height];

      this.eye_[0] = base.clamp(this.eye_[0], xLimits[0], xLimits[1]);
      this.eye_[1] = base.clamp(this.eye_[1], yLimits[0], yLimits[1]);

      this.dispatchRenderEvent_();
    },

    updateZoomByDelta: function(delta) {
      // Negative number should map to (0, 1)
      // and positive should map to (1, ...).
      var deltaY = delta[1];
      deltaY = base.clamp(deltaY, -50, 50);
      var scale = 1.0 + deltaY / 100.0;
      var zoomPoint = this.zoomPoint_;

      var originalScale = this.scale_;

      var pointOnSurface = [
        (zoomPoint[0] - this.eye_[0]) * this.scale_,
        (zoomPoint[1] - this.eye_[1]) * this.scale_];

      // Update scale.
      this.scale_ = base.clamp(this.scale_ * scale,
                               constants.MINIMUM_SCALE,
                               constants.MAXIMUM_SCALE);

      // Now see where the zoom point is on the surface with new scale.
      var newPointOnSurface = [
        (zoomPoint[0] - this.eye_[0]) * this.scale_,
        (zoomPoint[1] - this.eye_[1]) * this.scale_];

      // Shift the eye so that the zoom point remains stationary.
      var moveDelta = [
        (pointOnSurface[0] - newPointOnSurface[0]) / originalScale,
        (pointOnSurface[1] - newPointOnSurface[1]) / originalScale];
      this.updatePanByDelta(moveDelta);

      this.dispatchRenderEvent_();
    },

    updateRotateByDelta: function(delta) {
      this.rotation_[0] += base.deg2rad(delta[1]);
      this.rotation_[1] += base.deg2rad(delta[0]);

      var tiltLimitInRad = base.deg2rad(constants.MAXIMUM_TILT);

      this.rotation_[0] =
          base.clamp(this.rotation_[0], -tiltLimitInRad, tiltLimitInRad);
      this.rotation_[1] =
          base.clamp(this.rotation_[1], -tiltLimitInRad, tiltLimitInRad);

      this.dispatchRenderEvent_();
    },


    // Event callbacks.
    onPanBegin_: function(e) {
      this.panning_ = true;
      this.lastMousePosition_ = this.getMousePosition_(e.data);
    },

    onPanUpdate_: function(e) {
      if (!this.panning_)
        return;

      var delta = this.getMouseDelta_(e.data, this.lastMousePosition_);
      this.lastMousePosition_ = this.getMousePosition_(e.data);
      this.updatePanByDelta(delta);
    },

    onPanEnd_: function(e) {
      this.panning_ = false;
    },

    onZoomBegin_: function(e) {
      this.zooming_ = true;

      var p = this.getMousePosition_(e.data);

      this.lastMousePosition_ = p;
      this.zoomPoint_ = p;
    },

    onZoomUpdate_: function(e) {
      if (!this.zooming_)
        return;

      var delta = this.getMouseDelta_(e.data, this.lastMousePosition_);
      this.lastMousePosition_ = this.getMousePosition_(e.data);
      this.updateZoomByDelta(delta);
    },

    onZoomEnd_: function(e) {
      this.zooming_ = false;
      this.zoomPoint_ = undefined;
    },

    onRotateBegin_: function(e) {
      this.rotating_ = true;
      this.lastMousePosition_ = this.getMousePosition_(e.data);
    },

    onRotateUpdate_: function(e) {
      if (!this.rotating_)
        return;

      var delta = this.getMouseDelta_(e.data, this.lastMousePosition_);
      this.lastMousePosition_ = this.getMousePosition_(e.data);
      this.updateRotateByDelta(delta);
    },

    onRotateEnd_: function(e) {
      this.rotating_ = false;
    },


    // Misc helper functions.
    getMousePosition_: function(data) {
      var rect = base.windowRectForElement(this.canvas_);
      return [(data.clientX - rect.x) * this.pixelRatio_,
              (data.clientY - rect.y) * this.pixelRatio_];
    },

    getMouseDelta_: function(data, p) {
      var newP = this.getMousePosition_(data);
      return [newP[0] - p[0], newP[1] - p[1]];
    },

    dispatchRenderEvent_: function() {
      base.dispatchSimpleEvent(this, 'renderrequired', false, false);
    }
  };

  return {
    Camera: Camera
  };
});
