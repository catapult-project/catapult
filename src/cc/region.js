// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');

base.exportTo('cc', function() {
  function RegionFromArray(array) {
    if (array.length % 4 != 0)
      throw new Error('Array must consist be a multiple of 4 in length');

    var r = new Region();
    for (var i = 0; i < array.length; i += 4) {
      r.rects.push(base.Rect.FromXYWH(array[i], array[i + 1],
                                      array[i + 2], array[i + 3]));
    }
    return r;
  }

  /**
   * @constructor
   */
  function Region() {
    this.rects = [];
  }

  Region.prototype = {
    __proto__: Region.prototype,

    rectIntersects: function(r) {
      for (var i = 0; i < this.rects.length; i++) {
        if (this.rects[i].intersects(r))
          return true;
      }
      return false;
    }
  };

  return {
    Region: Region,
    RegionFromArray: RegionFromArray
  };
});
