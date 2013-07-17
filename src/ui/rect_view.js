// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview RectView is used to visualize a rect.
 */

base.exportTo('ui', function() {
  // Area above the RectView used draw decorations.
  var DECORATION_HEIGHT = 36;

  /**
   * @constructor
   */
  var RectView = ui.define('rect-view');

  RectView.prototype = {
    __proto__: HTMLUnknownElement.prototype,

    decorate: function() {
      this.viewport_ = undefined;
      this.rect_ = undefined;
    },

    set viewport(viewport) {
      this.viewport_ = viewport;
      this.updateContents_();
    },

    set rect(rect) {
      this.rect_ = rect;
      this.updateContents_();
    },

    updateContents_: function() {
      if (this.viewport_ === undefined || this.rect_ === undefined)
        return;

      var devicePixelsPerLayoutPixel = 1 / this.viewport_.devicePixelRatio;

      var topLeft = vec2.fromValues(this.rect_.x, this.rect_.y);
      var botRight = vec2.fromValues(
          topLeft[0] + this.rect_.width,
          topLeft[1] + this.rect_.height);
      vec2.transformMat2d(topLeft, topLeft,
          this.viewport_.getWorldToDevicePixelsTransform());
      vec2.scale(topLeft, topLeft, devicePixelsPerLayoutPixel);
      vec2.transformMat2d(botRight, botRight,
          this.viewport_.getWorldToDevicePixelsTransform());
      vec2.scale(botRight, botRight, devicePixelsPerLayoutPixel);
      this.style.width = botRight[0] - topLeft[0] + 'px';
      this.style.height = DECORATION_HEIGHT + botRight[1] - topLeft[1] + 'px';
      this.style.left = topLeft[0] + 'px';
      this.style.top = DECORATION_HEIGHT + topLeft[1] + 'px';
      this.style.backgroundSize = 'auto ' + DECORATION_HEIGHT + 'px';
    }

  };

  return {
    RectView: RectView
  };
});
