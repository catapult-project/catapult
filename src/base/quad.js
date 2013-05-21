// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.gl_matrix');

base.exportTo('base', function() {
  function QuadFromXYWH(x, y, w, h) {
    var q = new Quad();
    vec2.set(q.p1, x, y);
    vec2.set(q.p2, x + w, y);
    vec2.set(q.p3, x + w, y + h);
    vec2.set(q.p4, x, y + h);
    return q;
  }

  function QuadFromRect(r) {
    return new QuadFromXYWH(
      r.x, r.y,
      r.width, r.height);
  }

  function QuadFrom4Vecs(p1, p2, p3, p4) {
    var q = new Quad();
    vec2.set(q.p1, p1[0], p1[1]);
    vec2.set(q.p2, p2[0], p2[1]);
    vec2.set(q.p3, p3[0], p3[1]);
    vec2.set(q.p4, p4[0], p4[1]);
    return q;
  }

  function QuadFrom8Array(arr) {
    if (arr.length != 8)
      throw new Error('Array must be 8 long');
    var q = new Quad();
    q.p1[0] = arr[0];
    q.p1[1] = arr[1];
    q.p2[0] = arr[2];
    q.p2[1] = arr[3];
    q.p3[0] = arr[4];
    q.p3[1] = arr[5];
    q.p4[0] = arr[6];
    q.p4[1] = arr[7];
    return q;
  };

  /**
   * @constructor
   */
  function Quad() {
    this.p1 = vec2.create();
    this.p2 = vec2.create();
    this.p3 = vec2.create();
    this.p4 = vec2.create();
  }

  Quad.prototype = {
    vecInside: function(vec) {
      return vecInTriangle2(vec, this.p1, this.p2, this.p3) ||
          vecInTriangle2(vec, this.p1, this.p3, this.p4);
    },

    copy: function() {
      var q = new Quad();
      vec2.copy(q.p1, this.p1);
      vec2.copy(q.p2, this.p2);
      vec2.copy(q.p3, this.p3);
      vec2.copy(q.p4, this.p4);
      return q;
    }
  };

  function sign(p1, p2, p3) {
    return (p1[0] - p3[0]) * (p2[1] - p3[1]) -
        (p2[0] - p3[0]) * (p1[1] - p3[1]);
  }

  function vecInTriangle2(pt, p1, p2, p3) {
    var b1 = sign(pt, p1, p2) < 0.0;
    var b2 = sign(pt, p2, p3) < 0.0;
    var b3 = sign(pt, p3, p1) < 0.0;
    return ((b1 == b2) && (b2 == b3));
  }

  return {
    vecInTriangle2: vecInTriangle2,
    Quad: Quad,
    QuadFromXYWH: QuadFromXYWH,
    QuadFromRect: QuadFromRect,
    QuadFrom4Vecs: QuadFrom4Vecs,
    QuadFrom8Array: QuadFrom8Array
  };
});
