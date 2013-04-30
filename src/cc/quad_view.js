/* Copyright (c) 2012 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
'use strict';

base.requireStylesheet('cc.quad_view');

base.require('ui');
base.require('cc.quad_view_viewport');

base.exportTo('cc', function() {

  function QuadViewSelection(quadView, quadIndices) {
    this.view = quadView;
    this.quadIndices = quadIndices;
  }

  var QuadView = ui.define('x-quad-view');

  QuadView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.title_ = '';
      this.quads_ = undefined;
      this.viewport_ = undefined;
      this.deviceViewportSizeForFrame_ = undefined;
      this.header_ = document.createElement('div');
      this.header_.className = 'header';
      this.canvas_ = document.createElement('canvas');
      this.appendChild(this.header_);
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

    get headerText() {
      return this.headerText_;
    },

    set headerText(headerText) {
      this.headerText_ = headerText;
      this.updateChildren_();
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
      this.header_.textContent = this.headerText_;
      var canvas = this.canvas_;
      if (!this.hasRequiredProprties_) {
        canvas.width = 0;
        canvas.height = 0;
        return;
      }

      this.redrawCanvas_();
    },

    redrawCanvas_: function() {
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
        if (!quad.backgroundColor)
          continue;
        if (quad.backgroundColor != lastBackgroundColor) {
          lastBackgroundColor = quad.backgroundColor;
          ctx.fillStyle = lastBackgroundColor;
        }
        ctx.beginPath();
        ctx.moveTo(quad.p1.x, quad.p1.y);
        ctx.lineTo(quad.p2.x, quad.p2.y);
        ctx.lineTo(quad.p3.x, quad.p3.y);
        ctx.lineTo(quad.p4.x, quad.p4.y);
        ctx.closePath();
        ctx.fill();
      }

      // Outlines.
      ctx.strokeStyle = 'rgb(128,128,128)';
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        ctx.beginPath();
        ctx.moveTo(quad.p1.x, quad.p1.y);
        ctx.lineTo(quad.p2.x, quad.p2.y);
        ctx.lineTo(quad.p3.x, quad.p3.y);
        ctx.lineTo(quad.p4.x, quad.p4.y);
        ctx.closePath();
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
        ctx.moveTo(quad.p1.x, quad.p1.y);
        ctx.lineTo(quad.p2.x, quad.p2.y);
        ctx.lineTo(quad.p3.x, quad.p3.y);
        ctx.lineTo(quad.p4.x, quad.p4.y);
        ctx.closePath();
        ctx.stroke();
      }

      if (this.deviceViewportSizeForFrame_) {
        ctx.lineWidth = vp.getDeviceLineWidthAssumingTransformIsApplied(2.0);
        ctx.strokeStyle = 'rgba(255,0,0,1)';
        ctx.strokeRect(0,
                       0,
                       this.deviceViewportSizeForFrame_.width,
                       this.deviceViewportSizeForFrame_.height);
      }

      ctx.restore();
    },

    createSelection_: function(quadIndices) {
      return new QuadViewSelection(this, quadIndices);
    },
    selectQuadsAtCanvasClientPoint: function(clientX, clientY) {
      var selection = this.createSelection_(
        this.findQuadsAtCanvasClientPoint(clientX, clientY));
      var e = new base.Event('selection-changed');
      e.selection = selection;
      this.dispatchEvent(e);
      this.viewport_.forceRedrawAll();
    },

    findQuadsAtCanvasClientPoint: function(clientX, clientY) {
      var bounds = this.canvas_.getBoundingClientRect();
      var vecInLayout = vec2.createXY(clientX - bounds.left,
                                      clientY - bounds.top);
      var vecInWorldPixels =
        this.viewport_.layoutPixelsToWorldPixels2(vecInLayout);
      var pointInWorldPixels = vec2.asPoint(vecInWorldPixels);

      var quads = this.quads_;
      var hitIndices = [];
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        var hit = base.pointInQuad2Pt(pointInWorldPixels,
                                       quad);
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
    QuadView: QuadView,
    QuadViewSelection: QuadViewSelection,
  }
});

