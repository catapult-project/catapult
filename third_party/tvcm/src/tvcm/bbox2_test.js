// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.bbox2');

tvcm.testSuite('tvcm.bbox2_test', function() {
  test('addVec2', function() {
    var bbox = new tvcm.BBox2();
    var x = vec2.create();
    vec2.set(x, 10, 10);
    bbox.addVec2(x);
    assertTrue(bbox.minVec2[0] == 10);
    assertTrue(bbox.minVec2[1] == 10);
    assertTrue(bbox.maxVec2[0] == 10);
    assertTrue(bbox.maxVec2[1] == 10);
    // Mutate x.
    vec2.set(x, 11, 11);

    // Bbox shouldn't have changed.
    assertTrue(bbox.minVec2[0] == 10);
    assertTrue(bbox.minVec2[1] == 10);
    assertTrue(bbox.maxVec2[0] == 10);
    assertTrue(bbox.maxVec2[1] == 10);
  });
});
