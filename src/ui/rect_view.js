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

    get decorationHeight() {
      return DECORATION_HEIGHT;
    },

    updateContents_: function() {
      if (this.viewport_ === undefined || this.rect_ === undefined)
        return;

      var topLeft = vec2.fromValues(this.rect_.x, this.rect_.y);
      var botRight = vec2.fromValues(
          topLeft[0] + this.rect_.width,
          topLeft[1] + this.rect_.height);

      topLeft = this.viewport_.worldPixelsToLayoutPixels(topLeft);
      botRight = this.viewport_.worldPixelsToLayoutPixels(botRight);

      this.style.width = botRight[0] - topLeft[0] + 'px';
      // Under box-sizing: border box,
      // our decoration counts in the element height.
      this.style.height = DECORATION_HEIGHT + botRight[1] - topLeft[1] + 'px';
      this.style.left = topLeft[0] + 'px';
      this.style.top = topLeft[1] + 'px';
      // The decoration image needs to be sized to our specification.
      this.style.backgroundSize = 'auto ' + DECORATION_HEIGHT + 'px';
    }

  };

  return {
    RectView: RectView
  };
});
