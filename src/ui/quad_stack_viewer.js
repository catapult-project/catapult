// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview QuadStackViewer controls the content and viewing angle a
 * QuadStack.
 */
base.requireStylesheet('ui.quad_stack_viewer');

base.requireTemplate('ui.quad_stack_viewer');

base.require('base.raf');
base.require('ui.quad_view');
base.require('ui.camera');
base.require('ui.mouse_mode_selector');
base.require('ui.mouse_tracker');

base.exportTo('ui', function() {
  var constants = {};
  constants.IMAGE_LOAD_RETRY_TIME_MS = 500;

  /**
   * @constructor
   */
  var QuadStackViewer = ui.define('quad-stack-viewer');

  QuadStackViewer.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.className = 'quad-stack-viewer';

      var node = base.instantiateTemplate('#quad-stack-viewer-template');
      this.appendChild(node);

      this.canvas_ = this.querySelector('#canvas');
      this.chromeImages_ = {
        left: this.querySelector('#chrome-left'),
        mid: this.querySelector('#chrome-mid'),
        right: this.querySelector('#chrome-right')
      };

      this.quadView_ = new ui.QuadView();
      this.trackMouse_();

      this.camera_ = new ui.Camera(this.mouseModeSelector_);
      this.camera_.addEventListener('renderrequired',
          this.onRenderRequired_.bind(this));
      this.cameraWasReset_ = false;
      this.camera_.canvas = this.canvas_;

      this.viewportRect_ = base.Rect.FromXYWH(0, 0, 0, 0);

      this.stackingDistance_ = 30;
      this.pixelRatio_ = window.devicePixelRatio || 1;
    },

    onStackingDistanceChange: function(e) {
      this.stackingDistance_ = parseInt(e.target.value);
      this.scheduleRender();
    },

    get mouseModeSelector() {
      return this.mouseModeSelector_;
    },

    get camera() {
      return this.camera_;
    },

    set quads(q) {
      this.quads_ = q;
      this.scheduleRender();
    },

    set deviceRect(rect) {
      if (!rect || rect.equalTo(this.deviceRect_))
        return;

      this.deviceRect_ = rect;
      this.camera_.deviceRect = rect;
      this.chromeQuad_ = undefined;
    },

    resize: function() {
      var width = parseInt(window.getComputedStyle(this.offsetParent).width);
      var height = parseInt(window.getComputedStyle(this.offsetParent).height);
      var rect = base.Rect.FromXYWH(0, 0, width, height);

      if (rect.equalTo(this.viewportRect_))
        return false;

      this.viewportRect_ = rect;
      this.style.width = width + 'px';
      this.style.height = height + 'px';
      this.canvas_.style.width = width + 'px';
      this.canvas_.style.height = height + 'px';
      this.canvas_.width = this.pixelRatio_ * width;
      this.canvas_.height = this.pixelRatio_ * height;
      if (!this.cameraWasReset_) {
        this.camera_.resetCamera();
        this.cameraWasReset_ = true;
      }
      return true;
    },

    readyToDraw: function() {
      // If src isn't set yet, set it to ensure we can use
      // the image to draw onto a canvas.
      if (!this.chromeImages_.left.src) {
        var leftContent =
            window.getComputedStyle(this.chromeImages_.left).content;
        leftContent = leftContent.replace(/url\((.*)\)/, '$1');

        var midContent =
            window.getComputedStyle(this.chromeImages_.mid).content;
        midContent = midContent.replace(/url\((.*)\)/, '$1');

        var rightContent =
            window.getComputedStyle(this.chromeImages_.right).content;
        rightContent = rightContent.replace(/url\((.*)\)/, '$1');

        this.chromeImages_.left.src = leftContent;
        this.chromeImages_.mid.src = midContent;
        this.chromeImages_.right.src = rightContent;
      }

      // If all of the images are loaded (height > 0), then
      // we are ready to draw.
      return (this.chromeImages_.left.height > 0) &&
             (this.chromeImages_.mid.height > 0) &&
             (this.chromeImages_.right.height > 0);
    },

    get chromeQuad() {
      if (this.chromeQuad_)
        return this.chromeQuad_;

      // Draw the chrome border into a separate canvas.
      var chromeCanvas = document.createElement('canvas');
      var offsetY = this.chromeImages_.left.height;

      chromeCanvas.width = this.deviceRect_.width;
      chromeCanvas.height = this.deviceRect_.height + offsetY;

      var leftWidth = this.chromeImages_.left.width;
      var midWidth = this.chromeImages_.mid.width;
      var rightWidth = this.chromeImages_.right.width;

      var chromeCtx = chromeCanvas.getContext('2d');
      chromeCtx.drawImage(this.chromeImages_.left, 0, 0);

      chromeCtx.save();
      chromeCtx.translate(leftWidth, 0);

      // Calculate the scale of the mid image.
      var s = (this.deviceRect_.width - leftWidth - rightWidth) / midWidth;
      chromeCtx.scale(s, 1);

      chromeCtx.drawImage(this.chromeImages_.mid, 0, 0);
      chromeCtx.restore();

      chromeCtx.drawImage(
          this.chromeImages_.right, leftWidth + s * midWidth, 0);

      // Construct the quad.
      var chromeRect = base.Rect.FromXYWH(
          this.deviceRect_.x,
          this.deviceRect_.y - offsetY,
          this.deviceRect_.width,
          this.deviceRect_.height + offsetY);
      var chromeQuad = base.Quad.FromRect(chromeRect);
      chromeQuad.stackingGroupId = this.maxStachingGroupId_ + 1;
      chromeQuad.imageData = chromeCtx.getImageData(
          0, 0, chromeCanvas.width, chromeCanvas.height);
      chromeQuad.shadowOffset = [0, 0];
      chromeQuad.shadowBlur = 5;
      chromeQuad.borderWidth = 3;
      this.chromeQuad_ = chromeQuad;
      return this.chromeQuad_;
    },

    scheduleRender: function() {
      if (this.redrawScheduled_)
        return false;
      this.redrawScheduled_ = true;
      base.requestAnimationFrame(this.render, this);
    },

    onRenderRequired_: function(e) {
      this.scheduleRender();
    },

    render: function() {
      this.redrawScheduled_ = false;

      if (!this.readyToDraw()) {
        setTimeout(this.scheduleRender.bind(this),
                   constants.IMAGE_LOAD_RETRY_TIME_MS);
        return;
      }

      if (!this.quads_)
        return;

      var ctx = this.canvas_.getContext('2d');
      if (!this.resize())
        ctx.clearRect(0, 0, this.canvas_.width, this.canvas_.height);

      var mv = this.camera_.modelViewMatrix;
      var p = this.camera_.projectionMatrix;

      // Calculate the quad stacks.
      var quadStacks = [];
      for (var i = 0; i < this.quads_.length; ++i) {
        var quad = this.quads_[i];
        var stackingId = quad.stackingGroupId;
        while (stackingId >= quadStacks.length)
          quadStacks.push([]);

        quadStacks[stackingId].push(quad);
      }

      var mvp = mat4.create();
      this.maxStackingGroupId_ = quadStacks.length;
      var stackingDistance = this.stackingDistance_ * this.camera_.scale;

      // Draw the quad stacks, raising each subsequent level.
      mat4.multiply(mvp, p, mv);
      for (var i = 0; i < quadStacks.length; ++i) {
        this.quadView_.drawQuadsToCanvas(this.canvas_, mvp, quadStacks[i]);

        mat4.translate(mv, mv, [0, 0, stackingDistance]);
        mat4.multiply(mvp, p, mv);
      }

      this.quadView_.drawQuadsToCanvas(this.canvas_, mvp, this.chromeQuad);

      var fontSize = parseInt(15 * this.pixelRatio_);
      ctx.font = fontSize + 'px Arial';
      ctx.fillStyle = 'rgb(0, 0, 0)';
      ctx.fillText(
          'Scale: ' + parseInt(this.camera_.scale * 100) + '%', 10, fontSize);
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
    },
  };

  return {
    QuadStackViewer: QuadStackViewer
  };
});
