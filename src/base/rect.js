// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview 2D Rectangle math.
 */
base.require('base.gl_matrix');

base.exportTo('base', function() {

  /**
   * Tracks a 2D bounding box.
   * @constructor
   */
  function Rect() {
    this.x = 0;
    this.y = 0;
    this.width = 0;
    this.height = 0;
  };
  Rect.FromXYWH = function(x, y, w, h) {
    var rect = new Rect();
    rect.x = x;
    rect.y = y;
    rect.width = w;
    rect.height = h;
    return rect;
  }
  Rect.FromArray = function(ary) {
    if (ary.length != 4)
      throw new Error('ary.length must be 4');
    var rect = new Rect();
    rect.x = ary[0];
    rect.y = ary[1];
    rect.width = ary[2];
    rect.height = ary[3];
    return rect;
  }

  Rect.prototype = {
    __proto__: Object.prototype,

    translateXY: function(x, y) {
      this.x += x;
      this.y += y;
    },

    enlarge: function(pad) {
      this.x -= pad;
      this.y -= pad;
      this.width += 2 * pad;
      this.height += 2 * pad;
    },

    get left() {
      return this.x;
    },

    get top() {
      return this.y;
    },

    get right() {
      return this.x + this.width;
    },

    get bottom() {
      return this.x + this.width;
    }
  };

  return {
    Rect: Rect
  };

});
