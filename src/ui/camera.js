// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('ui', function() {

  var constants = {
    DEFAULT_ZOOM: 0.5, // needs to be large enough to fill view
    DEFAULT_Z_OFFSET_RATIO_TO_WORLD_SIZE: 0.02,
    MAXIMUM_ZOOM: 2.0,
    RESCALE_TIMEOUT_MS: 200,
    MAXIMUM_TILT: 75, // degrees
  };


  /**
   * @constructor
   */
  function Camera(targetElement) {
    this.quadStack_ = targetElement;

    this.scheduledLayoutPixelsPerWorldPixel_ = constants.DEFAULT_ZOOM;
    this.tiltAroundXInDegrees_ = 0;
    this.tiltAroundYInDegrees_ = 0;
    this.panXInLayoutPixels_ = 0;
    this.panYInLayoutPixels_ = 0;
    this.thicknessRatio = constants.DEFAULT_Z_OFFSET_RATIO_TO_WORLD_SIZE;

    this.quadStack_.addEventListener('layersChange',
        this.scheduleRepaint.bind(this));

    this.quadStack_.addEventListener('viewportChange', function(event) {
      var viewport = event.newValue;
      if (viewport) {
        viewport.addEventListener('change', this.scheduleRepaint.bind(this));
      }
    }.bind(this));

    window.addEventListener('resize', function() {
      delete this.maximumPanRectCache_;
    }.bind(this));

  }

  Camera.prototype = {

    get scheduledLayoutPixelsPerWorldPixel() {
      return this.scheduledLayoutPixelsPerWorldPixel_;
    },

    set scheduledLayoutPixelsPerWorldPixel(newValue) {
      var maxZoom = this.zoomLimitsVec2();
      if (newValue < maxZoom[0])
        return;
      if (newValue > maxZoom[1])
        return;
      this.scheduledLayoutPixelsPerWorldPixel_ = newValue;
      this.scheduleRescale_();
      this.scheduleRepaint();
    },

    get tiltAroundXInDegrees() {
      return this.tiltAroundXInDegrees_;
    },

    set tiltAroundXInDegrees(tilt) {
      if (Math.abs(tilt) > constants.MAXIMUM_TILT) {
        tilt = sign(tilt) * constants.MAXIMUM_TILT;
        return;
      }

      this.tiltAroundXInDegrees_ = tilt;
      this.scheduleRepaint();
    },

    get tiltAroundYInDegrees() {
      return this.tiltAroundYInDegrees_;
    },

    set tiltAroundYInDegrees(tilt) {
      if (Math.abs(tilt) > constants.MAXIMUM_TILT)
        return;
      this.tiltAroundYInDegrees_ = tilt;
      this.scheduleRepaint();
    },

    get panXInLayoutPixels() {
      return this.panXInLayoutPixels_;
    },

    set panXInLayoutPixels(newValue) {
      if (newValue < this.maximumPanRect.x)
        return;
      if (newValue > this.maximumPanRect.x + this.maximumPanRect.width)
        return;
      this.panXInLayoutPixels_ = newValue;
      this.scheduleRepaint();
    },

    get panYInLayoutPixels() {
      return this.panYInLayoutPixels_;
    },

    set panYInLayoutPixels(newValue) {
      if (newValue < this.maximumPanRect.y)
        return;
      if (newValue > this.maximumPanRect.y + this.maximumPanRect.height)
        return;
      this.panYInLayoutPixels_ = newValue;
      this.scheduleRepaint();
    },

    get maximumPanRect() {
      // TODO rely on cache
      this.maximumPanRectCache_ = this.maximumPanRect_();
      return this.maximumPanRectCache_;
    },

    get interimCSSScale() {
      return this.scheduledLayoutPixelsPerWorldPixel_ /
          this.quadStack_.viewport.layoutPixelsPerWorldPixel;
    },

    scheduleRepaint: function() {
      if (this.repaintPending_)
        return;
      delete this.maximumPanRectCache_;
      this.repaintPending_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.repaint_, this);
    },

    /** Call only inside of a requestAnimationFrame. */
    repaint: function() {
      this.repaintPending_ = true;
      this.repaint_();
    },

    zoomToFillViewWithWorld: function() {
      var elementPixelsPerLayoutPixel = this.scaleToFillViewWithLayout();
      return elementPixelsPerLayoutPixel *
          this.quadStack_.viewport.layoutPixelsPerWorldPixel;
    },

    scaleToFillViewWithLayout: function() {
      var containerElementRect =
          this.quadStack_.parentElement.getBoundingClientRect();
      var layoutRect = this.quadStack_.viewport.layoutRect;
      var widthScale = containerElementRect.width / layoutRect.width;
      var heightScale = containerElementRect.height / layoutRect.height;

      if (widthScale > 0 && heightScale > 0)
        return Math.min(widthScale, heightScale);
      return widthScale || heightScale || 1.0;
    },

    zoomLimitsVec2: function() {
      var min = 0.9 * this.zoomToFillViewWithWorld();
      var max = constants.MAXIMUM_ZOOM;
      return vec2.fromValues(min, max);
    },

    maximumPanRect_: function() {
      // Any value in this function that changes must cause
      // delete on this.maximumPanRectCache_.
      // Depends on viewport.
      var rect = this.quadStack_.viewport.layoutRect.clone();
      // Depends on cssScale
      rect = rect.scale(this.interimCSSScale);
      // Depends on resize.
      var eltRect = this.quadStack_.parentElement.getBoundingClientRect();

      if (rect.width > eltRect.width)
        rect.width = rect.width - eltRect.width;
      else
        rect.width = eltRect.width - rect.width;
      rect.x = -rect.width / 2;

      if (rect.height > eltRect.height)
        rect.height = rect.height - eltRect.height;
      else
        rect.height = eltRect.height - rect.height;
      rect.y = -rect.height / 2;
      return rect;
    },

    centerInLayoutUnitsVec2_: function() {
      var vp = this.quadStack_.viewport;
      var objectRect = vp.layoutRect;
      return vec2.createXY(
          objectRect.width / 2,
          objectRect.height / 2);
    },

    panInLayoutPixelsVec2_: function(cssScale) {
      return vec2.fromValues(this.panXInLayoutPixels, this.panYInLayoutPixels);
    },

    centeringPanInLayoutUnitsVec2_: function() {
      var objectCenter = this.centerInLayoutUnitsVec2_();
      var viewClientRect =
          this.quadStack_.parentElement.getBoundingClientRect();
      var viewCenter = vec2.createXY(
          viewClientRect.width / 2,
          viewClientRect.height / 2);

      var deltaCenter = vec2.create();
      vec2.subtract(deltaCenter, viewCenter, objectCenter);
      return deltaCenter;
    },

    rebasePanInLayoutPixels_: function(cssScale) {
      var basePan = this.centeringPanInLayoutUnitsVec2_();
      var pan = vec2.create();
      vec2.add(pan, basePan, this.panInLayoutPixelsVec2_());
      return pan;
    },

    originAtPanInLayoutPixels_: function() {
      var center = this.centerInLayoutUnitsVec2_();
      var origin = vec2.create();
      vec2.subtract(origin, center, this.panInLayoutPixelsVec2_());
      return origin;
    },

    translateLayersByZ_: function(worldRect, layers, cssScale) {
      var artificalThickness = this.thicknessRatio *
          Math.min(worldRect.width, worldRect.height);
      artificalThickness = Math.max(artificalThickness, 15);

      // Set depth of each layer such that they center around 0.
      var numLayers = layers.length;
      var deepestLayerZ = -artificalThickness * 0.5;
      var depthIncreasePerLayer = artificalThickness /
          Math.max(1, numLayers - 1);
      for (var i = 0; i < numLayers; i++) {
        var layer = layers[i];
        var newDepth = deepestLayerZ + i * depthIncreasePerLayer;
        newDepth = newDepth / cssScale;
        layer.style.webkitTransform = 'translateZ(' + newDepth + 'px)';
      }
    },

    shiftOriginToScaleAroundPan_: function(container, cssScale) {
      if (cssScale !== 1) {
        this.origin_ = this.originAtPanInLayoutPixels_();
        container.style.webkitTransformOrigin =
            this.origin_[0] + 'px ' + this.origin_[1] + 'px ';
      } else {
        container.style.webkitTransformOrigin = '';
      }
    },

    repaint_: function() {
      if (!this.repaintPending_)
        return;

      this.repaintPending_ = false;
      var layers = this.quadStack_.layers;

      if (!layers)
        return;

      var vp = this.quadStack_.viewport;
      var container = this.quadStack_.transformedContainer;

      var cssScale = this.interimCSSScale;

      this.translateLayersByZ_(vp.worldRect, layers, cssScale);
      this.shiftOriginToScaleAroundPan_(container, cssScale);

      var transformString = '';

      var panInLayoutPixels =
          this.rebasePanInLayoutPixels_(cssScale);
      transformString += ' translateX(' + panInLayoutPixels[0] + 'px)';
      transformString += ' translateY(' + panInLayoutPixels[1] + 'px)';

      transformString += ' scale(' + cssScale + ')';

      transformString += ' rotateX(' + this.tiltAroundXInDegrees_ + 'deg)';
      transformString += ' rotateY(' + this.tiltAroundYInDegrees_ + 'deg)';
      container.style.webkitTransform = transformString;
    },

    scheduleRescale_: function() {
      if (this.rescaleTimeoutID_) {
        clearTimeout(this.rescaleTimeoutID_);
      }
      this.rescaleTimeoutID_ = setTimeout(this.rescale_.bind(this),
          constants.RESCALE_TIMEOUT_MS);
    },

    rescalePanToMaintainOrigin_: function() {
      this.panXInLayoutPixels_ *= this.scheduledLayoutPixelsPerWorldPixel_;
      this.panYInLayoutPixels_ *= this.scheduledLayoutPixelsPerWorldPixel_;
    },

    rescale_: function() {
      delete this.rescaleTimeoutID_;
      this.rescalePanToMaintainOrigin_();
      var vp = this.quadStack_.viewport;
      vp.devicePixelsPerWorldPixel = this.scheduledLayoutPixelsPerWorldPixel_ *
          vp.devicePixelsPerLayoutPixel;
    }

  };

  return {
    Camera: Camera
  };
});
