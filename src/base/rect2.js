// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
'use strict';

/**
 * @fileoverview Quick range computations.
 */
base.require('base.gl_matrix');

base.exportTo('base', function() {

  /**
   * Tracks a 2D bounding box.
   * @constructor
   */
  function Rect2() {
    this.left = 0;
    this.top = 0;
    this.width = 0;
    this.height = 0;
  };
  Rect2.FromXYWH = function(x, y, w, h) {
    var rect = new Rect2();
    rect.left = x;
    rect.top = y;
    rect.width = w;
    rect.height = h;
    return rect;
  }

  Rect2.prototype = {
    __proto__: Object.prototype,

    translateXY: function(x, y) {
      this.left += x;
      this.top += y;
    },

    enlarge: function(pad) {
      this.left -= pad;
      this.top -= pad;
      this.width += 2*pad;
      this.height += 2*pad;
    },

    get right() {
      return this.left + this.width;
    },

    get bottom() {
      return this.left + this.width;
    }
  };

  return {
    Rect2: Rect2
  };

});
