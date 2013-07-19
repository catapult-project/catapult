// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('ui.quad_view');

base.require('base.color');
base.require('base.events');
base.require('base.raf');
base.require('ui');
base.require('ui.quad_view_viewport');

base.exportTo('ui', function() {
  // FIXME(pdr): Remove this extra scaling so our rasters are pixel-perfect.
  //             https://code.google.com/p/trace-viewer/issues/detail?id=228
  // FIXME(jjb): simplify until we have the camera working (or 228 happens ;-)
  var RASTER_SCALE = 1.0; // Adjust the resolution of our backing canvases.

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

  var QuadView = ui.define('quad-view');

  QuadView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      base.EventTargetHelper.decorate(this);

      this.quads_ = undefined;
      this.viewport_ = undefined;
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
      this.viewport_ = this.viewport_ ||
          this.createViewportFromQuads_(this.quads_);
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

      this.scheduleRedrawCanvas_();
    },

    scheduleRedrawCanvas_: function() {
      if (this.redrawScheduled_)
        return false;
      this.redrawScheduled_ = true;
      base.requestAnimationFrameInThisFrameIfPossible(
          this.redrawCanvas_, this);
    },

    redrawCanvas_: function() {
      this.redrawScheduled_ = false;

      var resizedCanvas = this.viewport_.updateBoxSize(this.canvas_);

      var ctx = this.canvas_.getContext('2d');

      var vp = this.viewport_;

      if (!resizedCanvas) // Canvas resizing automatically clears the context.
        ctx.clearRect(0, 0, this.canvas_.width, this.canvas_.height);

      ctx.save();
      ctx.scale(ui.RASTER_SCALE, ui.RASTER_SCALE);

      // The quads are in the world coordinate system. We are drawing
      // into a canvas with 0,0 in the top left corner. Tell the canvas to
      // transform drawing ops from world to canvas coordinates.
      vp.applyTransformToContext(ctx);
      ctx.lineWidth = vp.getDeviceLineWidthAssumingTransformIsApplied(1.0);

      var quads = this.quads_ || [];

      // Background colors.
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (quad.canvas) {
          if (quad.isRectangle()) {
            var bounds = quad.boundingRect();
            ctx.drawImage(quad.canvas, 0, 0,
                quad.canvas.width, quad.canvas.height,
                bounds.x, bounds.y, bounds.width, bounds.height);
          } else {
            ctx.save();
            var quadBBox = new base.BBox2();
            quadBBox.addQuad(quad);
            var iw = quad.canvas.width;
            var ih = quad.canvas.height;
            drawTexturedTriangle(
                ctx, quad.canvas,
                quad.p1[0], quad.p1[1],
                quad.p2[0], quad.p2[1],
                quad.p4[0], quad.p4[1],
                0, 0, iw, 0, 0, ih);
            drawTexturedTriangle(
                ctx, quad.canvas,
                quad.p2[0], quad.p2[1],
                quad.p3[0], quad.p3[1],
                quad.p4[0], quad.p4[1],
                iw, 0, iw, ih, 0, ih);
            ctx.restore();
          }
        }

        if (quad.backgroundColor) {
          ctx.fillStyle = quad.backgroundColor;
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
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        if (!quad.upperBorderColor)
          continue;
        if (document.activeElement == this.canvas_) {
          var tmp = base.Color.fromString(quad.upperBorderColor).brighten(0.25);
          ctx.strokeStyle = tmp.toString();
        } else {
          ctx.strokeStyle = quad.upperBorderColor;
        }

        ctx.beginPath();
        ctx.moveTo(quad.p1[0], quad.p1[1]);
        ctx.lineTo(quad.p2[0], quad.p2[1]);
        ctx.lineTo(quad.p3[0], quad.p3[1]);
        ctx.lineTo(quad.p4[0], quad.p4[1]);
        ctx.closePath();
        ctx.stroke();
      }

      ctx.restore();
    },

    selectQuadsAtCanvasClientPoint: function(clientX, clientY) {
      clientX *= ui.RASTER_SCALE;
      clientY *= ui.RASTER_SCALE;
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
          this.viewport_.layoutPixelsToWorldPixels(vecInLayout);

      var quads = this.quads_;
      var hitIndices = [];
      for (var i = 0; i < quads.length; i++) {
        var hit = quads[i].vecInside(vecInWorldPixels);
        if (hit)
          hitIndices.push(i);
      }
      return hitIndices;
    },

    createViewportFromQuads_: function() {
      var quads = this.quads_ || [];
      var quadBBox = new base.BBox2();
      quads.forEach(function(quad) {
        quadBBox.addQuad(quad);
      });
      return new ui.QuadViewViewport(quadBBox.asRect());
    },

    onMouseDown_: function(e) {
      if (!this.hasEventListener('selectionChanged'))
        return;
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
    RASTER_SCALE: RASTER_SCALE
  };
});
