// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview QuadStackView controls the content and viewing angle a
 * QuadStack.
 */
base.requireStylesheet('ui.quad_stack_view');

base.requireTemplate('ui.quad_stack_view');

base.require('base.raf');
base.require('ui.camera');
base.require('ui.mouse_mode_selector');
base.require('ui.mouse_tracker');

base.exportTo('ui', function() {
  var constants = {};
  constants.IMAGE_LOAD_RETRY_TIME_MS = 500;

  // Care of bckenney@ via
  // http://extremelysatisfactorytotalitarianism.com/blog/?p=2120
  function drawTexturedTriangle(
      ctx,
      img, x0, y0, x1, y1, x2, y2,
      u0, v0, u1, v1, u2, v2) {

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.closePath();

    x1 -= x0;
    y1 -= y0;
    x2 -= x0;
    y2 -= y0;

    u1 -= u0;
    v1 -= v0;
    u2 -= u0;
    v2 -= v0;

    var det = 1 / (u1 * v2 - u2 * v1),

        // linear transformation
        a = (v2 * x1 - v1 * x2) * det,
        b = (v2 * y1 - v1 * y2) * det,
        c = (u1 * x2 - u2 * x1) * det,
        d = (u1 * y2 - u2 * y1) * det,

        // translation
        e = x0 - a * u0 - c * v0,
        f = y0 - b * u0 - d * v0;

    ctx.save();
    ctx.transform(a, b, c, d, e, f);
    ctx.clip();
    ctx.drawImage(img, 0, 0);
    ctx.restore();
  }

  // Created to avoid creating garbage when doing bulk transforms.
  var tmp_vec4 = vec4.create();
  function transform(transformed, point, matrix) {
    vec4.set(tmp_vec4, point[0], point[1], 0, 1);
    vec4.transformMat4(tmp_vec4, tmp_vec4, matrix);

    transformed[0] = tmp_vec4[0] / tmp_vec4[3];
    transformed[1] = tmp_vec4[1] / tmp_vec4[3];
  }

  function drawProjectedQuadBackgroundToContext(
      quad, p1, p2, p3, p4, ctx, quadCanvas) {
    if (quad.imageData) {
      quadCanvas.width = quad.imageData.width;
      quadCanvas.height = quad.imageData.height;
      quadCanvas.getContext('2d').putImageData(quad.imageData, 0, 0);
      ctx.save();
      var quadBBox = new base.BBox2();
      quadBBox.addQuad(quad);
      var iw = quadCanvas.width;
      var ih = quadCanvas.height;
      drawTexturedTriangle(
          ctx, quadCanvas,
          p1[0], p1[1],
          p2[0], p2[1],
          p4[0], p4[1],
          0, 0, iw, 0, 0, ih);
      drawTexturedTriangle(
          ctx, quadCanvas,
          p2[0], p2[1],
          p3[0], p3[1],
          p4[0], p4[1],
          iw, 0, iw, ih, 0, ih);
      ctx.restore();
    }

    if (quad.backgroundColor) {
      ctx.fillStyle = quad.backgroundColor;
      ctx.beginPath();
      ctx.moveTo(p1[0], p1[1]);
      ctx.lineTo(p2[0], p2[1]);
      ctx.lineTo(p3[0], p3[1]);
      ctx.lineTo(p4[0], p4[1]);
      ctx.closePath();
      ctx.fill();
    }
  }

  function drawProjectedQuadOutlineToContext(
      quad, p1, p2, p3, p4, ctx, quadCanvas) {
    ctx.beginPath();
    ctx.moveTo(p1[0], p1[1]);
    ctx.lineTo(p2[0], p2[1]);
    ctx.lineTo(p3[0], p3[1]);
    ctx.lineTo(p4[0], p4[1]);
    ctx.closePath();
    ctx.save();
    if (quad.borderColor)
      ctx.strokeStyle = quad.borderColor;
    else
      ctx.strokeStyle = 'rgb(128,128,128)';

    if (quad.shadowOffset) {
      ctx.shadowColor = 'rgb(0, 0, 0)';
      ctx.shadowOffsetX = quad.shadowOffset[0];
      ctx.shadowOffsetY = quad.shadowOffset[1];
      if (quad.shadowBlur)
        ctx.shadowBlur = quad.shadowBlur;
    }

    if (quad.borderWidth)
      ctx.lineWidth = quad.borderWidth;
    else
      ctx.lineWidth = 1;

    ctx.stroke();
    ctx.restore();
  }

  function drawProjectedQuadSelectionOutlineToContext(
      quad, p1, p2, p3, p4, ctx, quadCanvas) {
    if (!quad.upperBorderColor)
      return;

    ctx.lineWidth = 8;
    ctx.strokeStyle = quad.upperBorderColor;

    ctx.beginPath();
    ctx.moveTo(p1[0], p1[1]);
    ctx.lineTo(p2[0], p2[1]);
    ctx.lineTo(p3[0], p3[1]);
    ctx.lineTo(p4[0], p4[1]);
    ctx.closePath();
    ctx.stroke();
  }

  function drawProjectedQuadToContext(
      passNumber, quad, p1, p2, p3, p4, ctx, quadCanvas) {
    if (passNumber === 0) {
      drawProjectedQuadBackgroundToContext(
          quad, p1, p2, p3, p4, ctx, quadCanvas);
    } else if (passNumber === 1) {
      drawProjectedQuadOutlineToContext(
          quad, p1, p2, p3, p4, ctx, quadCanvas);
    } else if (passNumber === 2) {
      drawProjectedQuadSelectionOutlineToContext(
          quad, p1, p2, p3, p4, ctx, quadCanvas);
    } else {
      throw new Error('Invalid pass number');
    }
  }

  var tmp_p1 = vec2.create();
  var tmp_p2 = vec2.create();
  var tmp_p3 = vec2.create();
  var tmp_p4 = vec2.create();
  function transformAndProcessQuads(
      matrix, quads, numPasses, handleQuadFunc, opt_arg1, opt_arg2) {

    for (var passNumber = 0; passNumber < numPasses; passNumber++) {
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        transform(tmp_p1, quad.p1, matrix);
        transform(tmp_p2, quad.p2, matrix);
        transform(tmp_p3, quad.p3, matrix);
        transform(tmp_p4, quad.p4, matrix);
        handleQuadFunc(passNumber, quad,
                       tmp_p1, tmp_p2, tmp_p3, tmp_p4,
                       opt_arg1, opt_arg2);
      }
    }
  }

  /**
   * @constructor
   */
  var QuadStackView = ui.define('quad-stack-view');

  QuadStackView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.className = 'quad-stack-view';

      var node = base.instantiateTemplate('#quad-stack-view-template');
      this.appendChild(node);

      this.canvas_ = this.querySelector('#canvas');
      this.chromeImages_ = {
        left: this.querySelector('#chrome-left'),
        mid: this.querySelector('#chrome-mid'),
        right: this.querySelector('#chrome-right')
      };

      this.trackMouse_();

      this.camera_ = new ui.Camera(this.mouseModeSelector_);
      this.camera_.addEventListener('renderrequired',
          this.onRenderRequired_.bind(this));
      this.cameraWasReset_ = false;
      this.camera_.canvas = this.canvas_;

      this.viewportRect_ = base.Rect.fromXYWH(0, 0, 0, 0);

      this.stackingDistance_ = 45;
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
      if (!this.offsetParent)
        return true;

      var width = parseInt(window.getComputedStyle(this.offsetParent).width);
      var height = parseInt(window.getComputedStyle(this.offsetParent).height);
      var rect = base.Rect.fromXYWH(0, 0, width, height);

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
      var chromeRect = base.Rect.fromXYWH(
          this.deviceRect_.x,
          this.deviceRect_.y - offsetY,
          this.deviceRect_.width,
          this.deviceRect_.height + offsetY);
      var chromeQuad = base.Quad.fromRect(chromeRect);
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

    stackTransformAndProcessQuads_: function(
        numPasses, handleQuadFunc, includeChromeQuad, opt_arg1, opt_arg2) {
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
        transformAndProcessQuads(mvp, quadStacks[i],
                                 numPasses, handleQuadFunc,
                                 opt_arg1, opt_arg2);

        mat4.translate(mv, mv, [0, 0, stackingDistance]);
        mat4.multiply(mvp, p, mv);
      }

      if (includeChromeQuad) {
        transformAndProcessQuads(mvp, [this.chromeQuad],
                                 numPasses, drawProjectedQuadToContext,
                                 opt_arg1, opt_arg2);
      }
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

      var canvasCtx = this.canvas_.getContext('2d');
      if (!this.resize())
        canvasCtx.clearRect(0, 0, this.canvas_.width, this.canvas_.height);

      var quadCanvas = document.createElement('canvas');
      this.stackTransformAndProcessQuads_(
          3, drawProjectedQuadToContext, true,
          canvasCtx, quadCanvas);
      quadCanvas.width = 0; // Hack: Frees the quadCanvas' resources.

      var fontSize = parseInt(15 * this.pixelRatio_);
      canvasCtx.font = fontSize + 'px Arial';
      canvasCtx.fillStyle = 'rgb(0, 0, 0)';
      canvasCtx.fillText(
          'Scale: ' + parseInt(this.camera_.scale * 100) + '%', 10, fontSize);
    },

    trackMouse_: function() {
      this.mouseModeSelector_ = new ui.MouseModeSelector(this);
      this.mouseModeSelector_.supportedModeMask =
          ui.MOUSE_SELECTOR_MODE.SELECTION |
          ui.MOUSE_SELECTOR_MODE.PANSCAN |
          ui.MOUSE_SELECTOR_MODE.ZOOM |
          ui.MOUSE_SELECTOR_MODE.ROTATE;
      this.mouseModeSelector_.mode = ui.MOUSE_SELECTOR_MODE.PANSCAN;
      this.mouseModeSelector_.pos = {x: 0, y: 100};
      this.appendChild(this.mouseModeSelector_);
      this.mouseModeSelector_.settingsKey =
          'quadStackView.mouseModeSelector';

      this.mouseModeSelector_.setModifierForAlternateMode(
          ui.MOUSE_SELECTOR_MODE.ROTATE, ui.MODIFIER.SHIFT);
      this.mouseModeSelector_.setModifierForAlternateMode(
          ui.MOUSE_SELECTOR_MODE.PANSCAN, ui.MODIFIER.SPACE);
      this.mouseModeSelector_.setModifierForAlternateMode(
          ui.MOUSE_SELECTOR_MODE.ZOOM, ui.MODIFIER.CMD_OR_CTRL);

      this.mouseModeSelector_.addEventListener('updateselection',
          this.onSelectionUpdate_.bind(this));
      this.mouseModeSelector_.addEventListener('endselection',
          this.onSelectionUpdate_.bind(this));
    },

    extractRelativeMousePosition_: function(e) {
      var br = this.canvas_.getBoundingClientRect();
      return [
        this.pixelRatio_ * (e.data.clientX - this.canvas_.offsetLeft - br.left),
        this.pixelRatio_ * (e.data.clientY - this.canvas_.offsetTop - br.top)
      ];
    },

    onSelectionUpdate_: function(e) {
      var mousePos = this.extractRelativeMousePosition_(e);
      var res = [];
      function handleQuad(passNumber, quad, p1, p2, p3, p4) {
        if (base.pointInImplicitQuad(mousePos, p1, p2, p3, p4))
          res.push(quad);
      }
      this.stackTransformAndProcessQuads_(1, handleQuad, false);
      var e = new Event('selectionchange', false, false);
      e.quads = res;
      this.dispatchEvent(e);
    }
  };

  return {
    QuadStackView: QuadStackView
  };
});
