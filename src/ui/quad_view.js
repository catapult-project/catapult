// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.color');
base.require('base.events');
base.require('base.raf');
base.require('ui');

base.exportTo('ui', function() {
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

  function transform(point, matrix) {
    var transformed = vec4.clone([point[0], point[1], 0, 1]);
    vec4.transformMat4(transformed, transformed, matrix);

    for (var i = 0; i < 4; ++i) {
      transformed[i] /= transformed[3];
    }
    return transformed;
  }

  function QuadView() {
  }

  QuadView.prototype = {
    drawQuadsToCanvas: function(canvas, matrix, quads) {
      var ctx = canvas.getContext('2d');
      if (!(quads instanceof Array))
        quads = [quads];

      var quadCanvas = document.createElement('canvas');

      // Background colors.
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        var p1 = transform(quad.p1, matrix);
        var p2 = transform(quad.p2, matrix);
        var p3 = transform(quad.p3, matrix);
        var p4 = transform(quad.p4, matrix);

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

      quadCanvas.width = 0; // Free the GPU texture.

      // Outlines.
      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        var p1 = transform(quad.p1, matrix);
        var p2 = transform(quad.p2, matrix);
        var p3 = transform(quad.p3, matrix);
        var p4 = transform(quad.p4, matrix);

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

      // Selection outlines.
      ctx.lineWidth = 8;

      for (var i = 0; i < quads.length; i++) {
        var quad = quads[i];
        var p1 = transform(quad.p1, matrix);
        var p2 = transform(quad.p2, matrix);
        var p3 = transform(quad.p3, matrix);
        var p4 = transform(quad.p4, matrix);

        if (!quad.upperBorderColor)
          continue;

        ctx.strokeStyle = quad.upperBorderColor;

        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.lineTo(p3[0], p3[1]);
        ctx.lineTo(p4[0], p4[1]);
        ctx.closePath();
        ctx.stroke();
      }
    }
  };

  return {
    QuadView: QuadView
  };
});
