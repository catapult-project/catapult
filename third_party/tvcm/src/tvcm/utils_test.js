// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.utils');

tvcm.unittest.testSuite('tvcm.utils_test', function() {
  test('clamping', function() {
    assertEquals(2, tvcm.clamp(2, 1, 3));
    assertEquals(1, tvcm.clamp(1, 1, 3));
    assertEquals(1, tvcm.clamp(0, 1, 3));
    assertEquals(3, tvcm.clamp(3, 1, 3));
    assertEquals(3, tvcm.clamp(4, 1, 3));
  });

  test('getUsingPath', function() {
    var z = tvcm.getUsingPath('x.y.z', {'x': {'y': {'z': 3}}});
    assertEquals(3, z);

    var w = tvcm.getUsingPath('x.w', {'x': {'y': {'z': 3}}});
    assertEquals(undefined, w);
  });
});
