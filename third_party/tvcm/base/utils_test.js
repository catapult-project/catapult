// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.utils');

base.unittest.testSuite('base.utils', function() {
  test('clamping', function() {
    assertEquals(2, base.clamp(2, 1, 3));
    assertEquals(1, base.clamp(1, 1, 3));
    assertEquals(1, base.clamp(0, 1, 3));
    assertEquals(3, base.clamp(3, 1, 3));
    assertEquals(3, base.clamp(4, 1, 3));
  });
});
