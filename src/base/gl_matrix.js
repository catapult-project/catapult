/* Copyright (c) 2012 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */
'use strict';

base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/common.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/mat2d.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/vec2.js');

base.exportTo('base', function() {
  var tmp_vec2 = vec2.create();
  var tmp_mat2d = mat2d.create();

  vec2.createXY = function(x, y) {
    var v = vec2.create();
    vec2.set(v, x, y);
    return v;
  };

  vec2.asPoint = function(v) {
    return {x: v[0],
            y: v[1]};
  }

  mat2d.translateInplace = function(inout, v) {
    mat2d.translate(tmp_mat2d, inout, v);
    mat2d.copy(inout, tmp_mat2d);
  }

  mat2d.translateInplaceXY = function(inout, x, y) {
    vec2.set(tmp_vec2, x, y);
    mat2d.translateInplace(inout, tmp_vec2);
  }

  mat2d.scaleInplace = function(inout, v) {
    mat2d.scale(tmp_mat2d, inout, v);
    mat2d.copy(inout, tmp_mat2d);
  }

  mat2d.scaleInplaceXY = function(inout, x, y) {
    vec2.set(tmp_vec2, x, y);
    mat2d.scaleInplace(inout, tmp_vec2);
  }

  mat2d.rotateInplace = function(inout, rad) {
    mat2d.rotate(tmp_mat2d, inout, rad);
    mat2d.copy(inout, tmp_mat2d);
  }

  function signPt(p1, p2, p3)
  {
    return (p1.x - p3.x) * (p2.y - p3.y) - (p2.x - p3.x) * (p1.y - p3.y);
  }

  function pointInTriangle2Pt(pt, p1, p2, p3)
  {
    var b1 = signPt(pt, p1, p2) < 0.0;
    var b2 = signPt(pt, p2, p3) < 0.0;
    var b3 = signPt(pt, p3, p1) < 0.0;
    return ((b1 == b2) && (b2 == b3));
  }

  function pointInQuad2Pt(pt, q)
  {
    return pointInTriangle2Pt(pt, q.p1, q.p2, q.p3) ||
           pointInTriangle2Pt(pt, q.p1, q.p3, q.p4);
  }

  return {
    pointInTriangle2Pt: pointInTriangle2Pt,
    pointInQuad2Pt: pointInQuad2Pt
  }
});
