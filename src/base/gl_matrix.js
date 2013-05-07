// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/common.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/mat2d.js');
base.requireRawScript('../third_party/gl-matrix/src/gl-matrix/vec2.js');

base.exportTo('base', function() {
  var tmp_vec2 = vec2.create();
  var tmp_mat2d = mat2d.create();

  vec2.createFromArray = function(arr) {
    if (arr.length != 2)
      throw new Error('Should be length 2');
    var v = vec2.create();
    vec2.set(v, arr[0], arr[1]);
    return v;
  };

  vec2.createXY = function(x, y) {
    var v = vec2.create();
    vec2.set(v, x, y);
    return v;
  };

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

  return {};
});
