// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.rect');

base.unittest.testSuite('base.rect', function() {
  test('UVRectBasic', function() {
    var container = base.Rect.FromXYWH(0, 0, 10, 10);
    var inner = base.Rect.FromXYWH(1, 1, 8, 8);
    var uv = inner.asUVRectInside(container);
    assertRectEquals(uv, base.Rect.FromXYWH(0.1, 0.1, .8, .8));
    assertEquals(container.size().width, 10);
    assertEquals(container.size().height, 10);
  });
});
