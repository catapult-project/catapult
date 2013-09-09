// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.sorted_array_utils');
base.require('tracing.color_scheme');
base.require('tracing.elided_cache');

/**
 * @fileoverview Provides various helper methods for drawing to a provided
 * canvas.
 */
base.exportTo('tracing', function() {
  var elidedTitleCache = new tracing.ElidedTitleCache();
  var palette = tracing.getColorPalette();
  var EventPresenter = tracing.EventPresenter;

  /**
   * Should we elide text on trace labels?
   * Without eliding, text that is too wide isn't drawn at all.
   * Disable if you feel this causes a performance problem.
   * This is a default value that can be overridden in tracks for testing.
   * @const
   */
  var SHOULD_ELIDE_TEXT = true;

  /**
   * Draw the define line into |ctx|.
   *
   * @param {Context} ctx The context to draw into.
   * @param {float} x1 The start x position of the line.
   * @param {float} y1 The start y position of the line.
   * @param {float} x2 The end x position of the line.
   * @param {float} y2 The end y position of the line.
   */
  function drawLine(ctx, x1, y1, x2, y2) {
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
  }

  /**
   * Draw the defined triangle into |ctx|.
   *
   * @param {Context} ctx The context to draw into.
   * @param {float} x1 The first corner x.
   * @param {float} y1 The first corner y.
   * @param {float} x2 The second corner x.
   * @param {float} y2 The second corner y.
   * @param {float} x3 The third corner x.
   * @param {float} y3 The third corner y.
   */
  function drawTriangle(ctx, x1, y1, x2, y2, x3, y3) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.lineTo(x3, y3);
    ctx.closePath();
  }

  /**
   * Draw an arrow into |ctx|.
   *
   * @param {Context} ctx The context to draw into.
   * @param {float} x1 The shaft x.
   * @param {float} y1 The shaft y.
   * @param {float} x2 The head x.
   * @param {float} y2 The head y.
   * @param {float} arrowLength The length of the head.
   * @param {float} arrowWidth The width of the head.
   */
  function drawArrow(ctx, x1, y1, x2, y2, arrowLength, arrowWidth) {
    var dx = x2 - x1;
    var dy = y2 - y1;
    var len = Math.sqrt(dx * dx + dy * dy);
    var perc = (len - arrowLength) / len;
    var bx = x1 + perc * dx;
    var by = y1 + perc * dy;
    var ux = dx / len;
    var uy = dy / len;
    var ax = uy * arrowWidth;
    var ay = -ux * arrowWidth;

    ctx.beginPath();
    drawLine(ctx, x1, y1, x2, y2);
    ctx.stroke();

    drawTriangle(ctx,
        bx + ax, by + ay,
        x2, y2,
        bx - ax, by - ay);
    ctx.fill();
  }

  /**
   * Draw the provided slices to the screen.
   *
   * Each of the elements in |slices| must provide the follow methods:
   *   * start
   *   * duration
   *   * colorId
   *   * selected
   *
   * @param {Context} ctx The canvas context.
   * @param {TimelineDrawTransform} dt The draw transform.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {float} viewHeight The height of the viewport.
   * @param {Array} slices The slices to draw.
   * @param {bool} async Whether the slices are drawn with async style.
   */
  function drawSlices(ctx, dt, viewLWorld, viewRWorld, viewHeight, slices,
                      async) {
    var pixelRatio = window.devicePixelRatio || 1;
    var pixWidth = dt.xViewVectorToWorld(1);
    var height = viewHeight * pixelRatio;

    // Begin rendering in world space.
    ctx.save();
    dt.applyTransformToCanvas(ctx);

    var tr = new tracing.FastRectRenderer(
        ctx, 2 * pixWidth, 2 * pixWidth, palette);
    tr.setYandH(0, height);

    var lowSlice = base.findLowIndexInSortedArray(
        slices,
        function(slice) { return slice.start + slice.duration; },
        viewLWorld);

    for (var i = lowSlice; i < slices.length; ++i) {
      var slice = slices[i];
      var x = slice.start;
      if (x > viewRWorld)
        break;

      var w = pixWidth;
      if (slice.duration > 0) {
        w = Math.max(slice.duration, 0.001);
        if (w < pixWidth)
          w = pixWidth;
      }

      var colorId = EventPresenter.getSliceColorId(slice);
      var alpha = EventPresenter.getSliceAlpha(slice, async);
      tr.fillRect(x, w, colorId, alpha);
    }
    tr.flush();
    ctx.restore();
  }

  /**
   * Draw the provided instant slices as lines to the screen.
   *
   * Each of the elements in |slices| must provide the follow methods:
   *   * start
   *   * duration with value of 0.
   *   * colorId
   *   * selected
   *
   * @param {Context} ctx The canvas context.
   * @param {TimelineDrawTransform} dt The draw transform.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {float} viewHeight The height of the viewport.
   * @param {Array} slices The slices to draw.
   * @param {Numer} lineWidthInPixels The width of the lines.
   */
  function drawInstantSlicesAsLines(
      ctx, dt, viewLWorld, viewRWorld, viewHeight, slices, lineWidthInPixels) {
    var pixelRatio = window.devicePixelRatio || 1;
    var height = viewHeight * pixelRatio;

    var pixWidth = dt.xViewVectorToWorld(1);

    // Begin rendering in world space.
    ctx.save();
    ctx.lineWidth = pixWidth * lineWidthInPixels;
    dt.applyTransformToCanvas(ctx);
    ctx.beginPath();

    var lowSlice = base.findLowIndexInSortedArray(
        slices,
        function(slice) { return slice.start; },
        viewLWorld);

    for (var i = lowSlice; i < slices.length; ++i) {
      var slice = slices[i];
      var x = slice.start;
      if (x > viewRWorld)
        break;

      ctx.strokeStyle = EventPresenter.getInstantSliceColor(slice);

      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    ctx.stroke();
    ctx.restore();
  }

  /**
   * Draws the labels for the given slices.
   *
   * The |slices| array must contain objects with the following API:
   *   * start
   *   * duration
   *   * title
   *   * didNotFinish (optional)
   *
   * @param {Context} ctx The graphics context.
   * @param {TimelineDrawTransform} dt The draw transform.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {Array} slices The slices to label.
   * @param {bool} async Whether the slice labels are drawn with async style.
   */
  function drawLabels(ctx, dt, viewLWorld, viewRWorld, slices, async) {
    var pixelRatio = window.devicePixelRatio || 1;
    var pixWidth = dt.xViewVectorToWorld(1);

    ctx.save();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = (10 * pixelRatio) + 'px sans-serif';

    if (async)
      ctx.font = 'italic ' + ctx.font;

    var lowSlice = base.findLowIndexInSortedArray(
        slices,
        function(slice) { return slice.start + slice.duration; },
        viewLWorld);

    // Don't render text until until it is 20px wide
    var quickDiscardThresshold = pixWidth * 20;
    for (var i = lowSlice; i < slices.length; ++i) {
      var slice = slices[i];
      if (slice.start > viewRWorld)
        break;

      if (slice.duration <= quickDiscardThresshold)
        continue;

      var title = slice.title +
          (slice.didNotFinish ? ' (Did Not Finish)' : '');

      var drawnTitle = title;
      var drawnWidth = elidedTitleCache.labelWidth(ctx, drawnTitle);
      var fullLabelWidth = elidedTitleCache.labelWidthWorld(
          ctx, drawnTitle, pixWidth);
      if (SHOULD_ELIDE_TEXT && fullLabelWidth > slice.duration) {
        var elidedValues = elidedTitleCache.get(
            ctx, pixWidth,
            drawnTitle, drawnWidth,
            slice.duration);
        drawnTitle = elidedValues.string;
        drawnWidth = elidedValues.width;
      }

      if (drawnWidth * pixWidth < slice.duration) {
        ctx.fillStyle = EventPresenter.getTextColor(slice);
        var cX = dt.xWorldToView(slice.start + 0.5 * slice.duration);
        ctx.fillText(drawnTitle, cX, 2.5 * pixelRatio, drawnWidth);
      }
    }
    ctx.restore();
  }

  return {
    drawSlices: drawSlices,
    drawInstantSlicesAsLines: drawInstantSlicesAsLines,
    drawLabels: drawLabels,

    drawLine: drawLine,
    drawTriangle: drawTriangle,
    drawArrow: drawArrow,

    elidedTitleCache_: elidedTitleCache
  };
});
