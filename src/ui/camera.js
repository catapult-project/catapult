// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('ui', function() {

  function lerp(a, b, interp) {
    return (a * (1 - interp)) +
        (b * interp);
  }

  /**
   * @constructor
   */
  function Camera(targetElement) {
    this.targetElement_ = targetElement;

    this.onMouseDown_ = this.onMouseDown_.bind(this);
    this.onMouseMove_ = this.onMouseMove_.bind(this);
    this.onMouseUp_ = this.onMouseUp_.bind(this);

    this.cameraStart_ = {x: 0, y: 0};
    this.rotations_ = {x: 0, y: 0};
    this.rotationStart_ = {x: 0, y: 0};
    this.matrixParameters_ = {
      thicknessRatio: 0.012, // Ratio of thickness to world size.
      strengthRatioX: 0.7, // Ratio of mousemove X pixels to degrees rotated.
      strengthRatioY: 0.25 // Ratio of mousemove Y pixels to degrees rotated.
    };

    this.targetElement_.addEventListener('mousedown', this.onMouseDown_);
    this.targetElement_.addEventListener('layersChange',
        this.scheduleRepaint.bind(this));
  }

  Camera.prototype = {

    scheduleRepaint: function() {
      if (this.repaintPending_)
        return;
      this.repaintPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.repaint_, this);
    },

    /** Call only inside of a requestAnimationFrame. */
    repaint: function() {
      this.repaintPending_ = true;
      this.repaint_();
    },

    repaint_: function() {
      if (!this.repaintPending_)
        return;

      this.repaintPending_ = false;
      var layers = this.targetElement_.layers;

      if (!layers)
        return;

      var numLayers = layers.length;

      var vpThickness;
      if (this.targetElement_.viewport) {
        vpThickness = this.matrixParameters_.thicknessRatio *
            Math.min(this.targetElement_.viewport.worldRect.width,
                     this.targetElement_.viewport.worldRect.height);
      } else {
        vpThickness = 0;
      }
      vpThickness = Math.max(vpThickness, 15);

      // When viewing the stack head-on, we want no foreshortening effects. As
      // we move off axis, let the thickness grow as well as the amount of
      // perspective foreshortening.
      var maxRotation = Math.max(Math.abs(this.rotations_.x),
                                 Math.abs(this.rotations_.y));
      var clampLimit = 30;
      var clampedMaxRotation = Math.min(maxRotation, clampLimit);
      var percentToClampLimit = clampedMaxRotation / clampLimit;
      var persp = Math.pow(Math.E,
                           lerp(Math.log(5000), Math.log(500),
                                percentToClampLimit));
      this.targetElement_.webkitPerspective = persp;
      var effectiveThickness = vpThickness * percentToClampLimit;

      // Set depth of each layer such that they center around 0.
      var deepestLayerZ = -effectiveThickness * 0.5;
      var depthIncreasePerLayer = effectiveThickness /
          Math.max(1, numLayers - 1);
      for (var i = 0; i < numLayers; i++) {
        var layer = layers[i];
        var newDepth = deepestLayerZ + i * depthIncreasePerLayer;
        layer.style.webkitTransform = 'translateZ(' + newDepth + 'px)';
      }

      // Set rotation matrix to whatever is stored.
      var transformString = '';
      transformString += 'rotateX(' + this.rotations_.x + 'deg)';
      transformString += ' rotateY(' + this.rotations_.y + 'deg)';
      var container = this.targetElement_.contentContainer;
      container.style.webkitTransform = transformString;
    },

    updateCameraStart_: function(x, y) {
      this.cameraStart_.x = x;
      this.cameraStart_.y = y;
      this.rotationStart_.x = this.rotations_.x;
      this.rotationStart_.y = this.rotations_.y;
    },

    updateCamera_: function(x, y) {
      var delta = {
        x: this.cameraStart_.x - x,
        y: this.cameraStart_.y - y
      };
      // update new rotation matrix (note the parameter swap)
      // "strength" is ration between mouse dist and rotation amount.
      this.rotations_.x = this.rotationStart_.x + delta.y *
          this.matrixParameters_.strengthRatioY;
      this.rotations_.y = this.rotationStart_.y + -delta.x *
          this.matrixParameters_.strengthRatioX;
      this.scheduleRepaint();
    },

    onMouseDown_: function(e) {
      this.updateCameraStart_(e.x, e.y);
      document.addEventListener('mousemove', this.onMouseMove_);
      document.addEventListener('mouseup', this.onMouseUp_);
      e.preventDefault();
      return true;
    },

    onMouseMove_: function(e) {
      this.updateCamera_(e.x, e.y);
    },

    onMouseUp_: function(e) {
      document.removeEventListener('mousemove', this.onMouseMove_);
      document.removeEventListener('mouseup', this.onMouseUp_);
      this.updateCamera_(e.x, e.y);
    },

  };

  return {
    Camera: Camera
  };
});
