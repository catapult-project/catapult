// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview QuadStackViewer controls the content and viewing angle a
 * QuadStack.
 */
base.requireStylesheet('ui.quad_stack_viewer');
base.require('ui.quad_stack');
base.require('ui.mouse_mode_selector');
base.require('ui.mouse_tracker');

base.exportTo('ui', function() {
  var constants = {
    MAX_TILT_DEGREES: 75
  };
  /**
   * @constructor
   */
  var QuadStackViewer = ui.define('quad-stack-viewer');

  QuadStackViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.className = 'quad-stack-viewer';
      this.scale_ = 0.25;

      this.quadStack_ = new ui.QuadStack();
      this.appendChild(this.quadStack_);

      this.camera_ = new ui.Camera(this.quadStack_);
      this.trackMouse_();
    },

    get mouseModeSelector() {
      return this.mouseModeSelector_;
    },

    get quadStack() {
      return this.quadStack_;
    },

    get camera() {
      return this.camera_;
    },

    fractionOfRange_: function(delta, rangeKey) {
      var range = this.getBoundingClientRect()[rangeKey];
      return delta / range;
    },

    deltaAngle_: function(fractionOfRange) {
      var angle = fractionOfRange * 2 * constants.MAX_TILT_DEGREES;
      return Math.max(-constants.MAX_TILT_DEGREES,
          Math.min(angle, constants.MAX_TILT_DEGREES));
    },

    pan: function(delta) {
      this.camera.panXInLayoutPixels += delta.x;
      this.camera.panYInLayoutPixels += delta.y;
    },

    tilt: function(delta) {
      this.camera.tiltAroundYInDegrees +=
          this.deltaAngle_(this.fractionOfRange_(delta.x, 'width'));
      this.camera.tiltAroundXInDegrees -=
          this.deltaAngle_(this.fractionOfRange_(delta.y, 'height'));
    },

    zoom: function(delta) {
      var zoomLimits = this.camera.zoomLimitsVec2();
      var rise = zoomLimits[1] - zoomLimits[0];
      this.camera.scheduledLayoutPixelsPerWorldPixel -=
          rise * this.fractionOfRange_(delta.y, 'height');
    },

    trackMouse_: function() {
      this.mouseModeSelector_ = new ui.MouseModeSelector(this);
      this.mouseModeSelector_.supportedModeMask =
          ui.MOUSE_SELECTOR_MODE.ALL_MODES;
      this.mouseModeSelector_.mode = ui.MOUSE_SELECTOR_MODE.PANSCAN;
      this.mouseModeSelector_.pos = {x: 0, y: 100};
      this.appendChild(this.mouseModeSelector_);
      this.mouseModeSelector_.settingsKey =
          'quadStackViewer.mouseModeSelector';

      this.addEventListener('updatepan', this.onUpdate_.bind(this, 'pan'));
      this.addEventListener('updatezoom', this.onUpdate_.bind(this, 'zoom'));
      this.addEventListener('updatetiming', this.onUpdate_.bind(this, 'tilt'));
    },

    /**
     * Wraps the standard addEventListener but automatically binds the provided
     * func to the provided target, tracking the resulting closure. When detach
     * is called, these listeners will be automatically removed.
     */
    bindListener_: function(object, event, func, target, prop) {
      if (!this.boundListeners_)
        this.boundListeners_ = [];
      var boundFunc = func.bind(target, prop);
      this.boundListeners_.push({object: object,
        event: event,
        boundFunc: boundFunc});
      object.addEventListener(event, boundFunc);
    },

    detach: function() {
      for (var i = 0; i < this.boundListeners_.length; i++) {
        var binding = this.boundListeners_[i];
        binding.object.removeEventListener(binding.event, binding.boundFunc);
      }
      this.boundListeners_ = undefined;
    },

    isSamePosition_: function(lhs, rhs) {
      return rhs && lhs.x === rhs.x && lhs.y === rhs.y;
    },

    onUpdate_: function(property, selectorEvent) {
      if (this.isSamePosition_(selectorEvent.mouseDownPosition,
          this.lastMouseDownPosition_))
        this.continueUpdate_(property, selectorEvent.data);
      else
        this.newUpdate_(property, selectorEvent);
    },

    continueUpdate_: function(property, mouseEvent) {;
      var mouseEventPosition = {x: mouseEvent.clientX, y: mouseEvent.clientY};
      var dx = mouseEventPosition.x - this.lastMousePosition_.x;
      var dy = mouseEventPosition.y - this.lastMousePosition_.y;
      this[property]({x: dx, y: dy});
      this.lastMousePosition_ = mouseEventPosition;
    },

    newUpdate_: function(property, selectorEvent) {
      this.lastMouseDownPosition_ = {
        x: selectorEvent.mouseDownPosition.x,
        y: selectorEvent.mouseDownPosition.y
      };
      this.lastMousePosition_ = {
        x: this.lastMouseDownPosition_.x,
        y: this.lastMouseDownPosition_.y
      };
      this.continueUpdate_(property, selectorEvent.data);
    },
  };

  return {
    QuadStackViewer: QuadStackViewer
  };
});
