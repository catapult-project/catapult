// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.quad_view');

base.require('ui');
base.require('ui.quad_view_viewport');

base.exportTo('ui', function() {

  var QuadView = ui.define('x-quad-view');

  QuadView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.quads_ = undefined;
      this.viewport_ = undefined;
      this.deviceViewportSizeForFrame_ = undefined;
      this.canvas_ = document.createElement('canvas');

      this.appendChild(this.canvas_);

      this.onViewportChanged_ = this.onViewportChanged_.bind(this);
      this.onMouseDown_ = this.onMouseDown_.bind(this);
      this.onMouseMove_ = this.onMouseMove_.bind(this);
      this.onMouseUp_ = this.onMouseUp_.bind(this);
      this.canvas_.addEventListener('mousedown', this.onMouseDown_);

      this.canvas_.addEventListener('focus', this.redrawCanvas_.bind(this));
      this.canvas_.addEventListener('blur', this.redrawCanvas_.bind(this));
      this.canvas_.tabIndex = 0;
    },

    get viewport() {
      return this.viewport_;
    },

    set viewport(viewport) {
      if (this.viewport_)
        this.viewport_.removeEventListener('change', this.onViewportChanged_);
      this.viewport_ = viewport;
      if (this.viewport_)
        this.viewport_.addEventListener('change', this.onViewportChanged_);
      this.updateChildren_();
    },

    onViewportChanged_: function() {
      if (!this.hasRequiredProprties_)
        return;
      this.redrawCanvas_();
    },

    get quads() {
      return this.quads_;
    },

    set quads(quads) {
      this.quads_ = quads;
      if (!this.quads_) {
        this.updateChildren_();
        return;
      }
      this.quads_.forEach(function(quad) {
        if (!quad.backgroundRasterData)
          return;
        var tex = quad.backgroundRasterData;
        var helperCanvas = document.createElement('canvas');
        helperCanvas.width = tex.width;
        helperCanvas.height = tex.height;
        var ctx = helperCanvas.getContext('2d');
        var imageData = ctx.createImageData(tex.width, tex.height);
        imageData.data.set(tex.data);
        ctx.putImageData(imageData, 0, 0);
        var img = document.createElement('img');
        img.onload = function() {
          quad.backgroundImage = img;
          this.scheduleRedrawCanvas_();
        }.bind(this);
        img.src = helperCanvas.toDataURL();
      }, this);
      this.updateChildren_();
    },

    get deviceViewportSizeForFrame() {
      return this.deviceViewportSizeForFrame_;
    },

    set deviceViewportSizeForFrame(size) {
      this.deviceViewportSizeForFrame_ = size;
      this.updateChildren_();
    },

    get hasRequiredProprties_() {
      return this.quads_ &&
          this.viewport_;
    },

    updateChildren_: function() {
      var canvas = this.canvas_;
      if (!this.hasRequiredProprties_) {
        canvas.width = 0;
        canvas.height = 0;
        return;
      }

      this.redrawCanvas_();
    },

    scheduleRedrawCanvas_: function() {
      if (this.redrawScheduled_)
        return false;
      this.redrawScheduled_ = true;
      window.webkitRequestAnimationFrame(this.redrawCanvas_.bind(this));
    },

    redrawCanvas_: function() {
      this.redrawScheduled_ = false;

      if (this.canvas_.width != this.viewport_.deviceWidth) {
        this.canvas_.width = this.viewport_.deviceWidth;
        this.canvas_.style.width = this.viewport_.layoutWidth + 'px';
      }
      if (this.canvas_.height != this.viewport_.deviceHeight) {
        this.canvas_.height = this.viewport_.deviceHeight;
        this.canvas_.style.height = this.viewport_.layoutHeight + 'px';
      }

      var ctx = this.canvas_.getContext('2d');

      var vp = this.viewport_;
      ctx.fillStyle = 'rgb(255,255,255)';
      ctx.fillRect(
          0, 0,
          this.canvas_.width, this.canvas_.height);
      ctx.save();

      vp.applyTransformToContext(ctx);
      ctx.lineWidth = vp.getDeviceLineWidthAssumingTransformIsApplied(1.0);

      var quads = this.quads_;

      // Background colors.
      var lastBackgroundColor = 'rgb(255,255,0)';
      ctx.fillStyle = lastBackgroundColor;
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (quad.backgroundImage) {
          ctx.save();
          var quadBBox = new base.BBox2();
          quadBBox.addQuad(quad);

          // TODO(nduca): Warp the image here to fil the quad.
          // Probably this: http://extremelysatisfactorytotalitarianism.com/blog/?p=2120
          // and this: https://github.com/mrdoob/three.js/blob/master/src/renderers/CanvasRenderer.js
          ctx.drawImage(quad.backgroundImage,
                        quadBBox.minVec2[0], quadBBox.minVec2[1],
                        quadBBox.size.width, quadBBox.size.height);
          ctx.restore();
        }

        if (quad.backgroundColor) {
          if (quad.backgroundColor != lastBackgroundColor) {
            lastBackgroundColor = quad.backgroundColor;
            ctx.fillStyle = lastBackgroundColor;
          }
          ctx.beginPath();
          ctx.moveTo(quad.p1[0], quad.p1[1]);
          ctx.lineTo(quad.p2[0], quad.p2[1]);
          ctx.lineTo(quad.p3[0], quad.p3[1]);
          ctx.lineTo(quad.p4[0], quad.p4[1]);
          ctx.closePath();
          ctx.fill();
        }
      }

      // Outlines.
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        ctx.beginPath();
        ctx.moveTo(quad.p1[0], quad.p1[1]);
        ctx.lineTo(quad.p2[0], quad.p2[1]);
        ctx.lineTo(quad.p3[0], quad.p3[1]);
        ctx.lineTo(quad.p4[0], quad.p4[1]);
        ctx.closePath();
        if (quad.borderColor)
          ctx.strokeStyle = quad.borderColor;
        else
          ctx.strokeStyle = 'rgb(128,128,128)';
        ctx.stroke();
      }

      // Selection outlines.
      ctx.lineWidth = vp.getDeviceLineWidthAssumingTransformIsApplied(8.0);
      var rules = window.getMatchedCSSRules(this.canvas_);

      // TODO(nduca): Figure out how to get these from css.
      if (document.activeElement == this.canvas_)
        ctx.strokeStyle = 'rgb(187,226,54)';
      else
        ctx.strokeStyle = 'rgb(156,189,45)';

      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (!quad.selected)
          continue;
        ctx.beginPath();
        ctx.moveTo(quad.p1[0], quad.p1[1]);
        ctx.lineTo(quad.p2[0], quad.p2[1]);
        ctx.lineTo(quad.p3[0], quad.p3[1]);
        ctx.lineTo(quad.p4[0], quad.p4[1]);
        ctx.closePath();
        ctx.stroke();
      }

      if (this.deviceViewportSizeForFrame_) {
        ctx.lineWidth = vp.getDeviceLineWidthAssumingTransformIsApplied(2.0);
        ctx.strokeStyle = 'rgba(0,0,255,1)';
        ctx.strokeRect(0,
                       0,
                       this.deviceViewportSizeForFrame_.width,
                       this.deviceViewportSizeForFrame_.height);
      }

      ctx.restore();
    },

    selectQuadsAtCanvasClientPoint: function(clientX, clientY) {
      var selectedQuadIndices = this.findQuadsAtCanvasClientPoint(
          clientX, clientY);
      var e = new base.Event('selectionChanged');
      e.selectedQuadIndices = selectedQuadIndices;
      this.dispatchEvent(e);
      this.viewport_.forceRedrawAll();
    },

    findQuadsAtCanvasClientPoint: function(clientX, clientY) {
      var bounds = this.canvas_.getBoundingClientRect();
      var vecInLayout = vec2.createXY(clientX - bounds.left,
                                      clientY - bounds.top);
      var vecInWorldPixels =
          this.viewport_.layoutPixelsToWorldPixels2(vecInLayout);

      var quads = this.quads_;
      var hitIndices = [];
      for (var i = 0; i < quads.length; i++) {
        var hit = quads[i].vecInside(vecInWorldPixels);
        if (hit)
          hitIndices.push(i);
      }
      return hitIndices;
    },

    onMouseDown_: function(e) {
      this.selectQuadsAtCanvasClientPoint(e.clientX, e.clientY);
      document.addEventListener('mousemove', this.onMouseMove_);
      document.addEventListener('mouseup', this.onMouseUp_);
      e.preventDefault();
      this.canvas_.focus();
      return true;
    },

    onMouseMove_: function(e) {
      this.selectQuadsAtCanvasClientPoint(e.clientX, e.clientY);
    },

    onMouseUp_: function(e) {
      this.selectQuadsAtCanvasClientPoint(e.clientX, e.clientY);
      document.removeEventListener('mousemove', this.onMouseMove_);
      document.removeEventListener('mouseup', this.onMouseUp_);
    }

  };

  return {
    QuadView: QuadView
  };
});
