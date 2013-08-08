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
  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  /**
   * Should we elide text on trace labels?
   * Without eliding, text that is too wide isn't drawn at all.
   * Disable if you feel this causes a performance problem.
   * This is a default value that can be overridden in tracks for testing.
   * @const
   */
  var SHOULD_ELIDE_TEXT = true;

  /**
   * Draw the define line into |ctx| in the given |color|.
   *
   * @param {Context} ctx The context to draw into.
   * @param {String} color The color to draw the lines.
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
   * Each arrow must have the following API:
   *   * x1, y1
   *   * x2, y2
   *   * x3, y3
   *   * color  optional
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
    ctx.lineTo(x1, y1);
    ctx.closePath();
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
   * @param {TimelineViewport} vp The viewport.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {float} viewHeight The height of the viewport.
   * @param {Array} slices The slices to draw.
   */
  function drawSlices(ctx, vp, viewLWorld, viewRWorld, viewHeight, slices) {
    var pixelRatio = window.devicePixelRatio || 1;
    var height = viewHeight * pixelRatio;

    var pixWidth = vp.xViewVectorToWorld(1);
    var palette = tracing.getColorPalette();

    // Begin rendering in world space.
    ctx.save();
    vp.applyTransformToCanvas(ctx);

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

      var colorId = slice.selected ?
          slice.colorId + highlightIdBoost :
          slice.colorId;

      tr.fillRect(x, w, colorId);
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
   * @param {TimelineViewport} vp The viewport.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {float} viewHeight The height of the viewport.
   * @param {Array} slices The slices to draw.
   * @param {Numer} lineWidthInPixels The width of the lines.
   */
  function drawInstantSlicesAsLines(
      ctx, vp, viewLWorld, viewRWorld, viewHeight, slices, lineWidthInPixels) {
    var pixelRatio = window.devicePixelRatio || 1;
    var height = viewHeight * pixelRatio;

    var pixWidth = vp.xViewVectorToWorld(1);
    var palette = tracing.getColorPalette();

    // Begin rendering in world space.
    ctx.save();
    ctx.lineWidth = pixWidth * lineWidthInPixels;
    vp.applyTransformToCanvas(ctx);
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

      var colorId = slice.selected ?
          slice.colorId + highlightIdBoost :
          slice.colorId;

      ctx.strokeStyle = palette[colorId];
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
   * @param {TimelineViewport} vp The viewport.
   * @param {float} viewLWorld The left most point of the world viewport.
   * @param {float} viewLWorld The right most point of the world viewport.
   * @param {Array} slices The slices to label.
   */
  function drawLabels(ctx, vp, viewLWorld, viewRWorld, slices) {
    var pixelRatio = window.devicePixelRatio || 1;
    var pixWidth = vp.xViewVectorToWorld(1);

    ctx.save();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.font = (10 * pixelRatio) + 'px sans-serif';
    ctx.strokeStyle = 'rgb(0,0,0)';
    ctx.fillStyle = 'rgb(0,0,0)';

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
        var cX = vp.xWorldToView(slice.start + 0.5 * slice.duration);
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

    elidedTitleCache_: elidedTitleCache
  };
});
