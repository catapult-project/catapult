// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.timeline_display_transform');

base.unittest.testSuite('tracing.timeline_display_transform', function() {
  var TimelineDisplayTransform = tracing.TimelineDisplayTransform;

  test('basics', function() {
    var a = new TimelineDisplayTransform();
    a.panX = 0;
    a.panY = 0;
    a.scaleX = 1;

    var b = new TimelineDisplayTransform();
    b.panX = 10;
    b.panY = 0;
    b.scaleX = 1;

    assertFalse(a.equals(b));
    assertFalse(a.almostEquals(b));

    var c = b.clone();
    assertTrue(b.equals(c));
    assertTrue(b.almostEquals(c));

    c.set(a);
    assertTrue(a.equals(c));
    assertTrue(a.almostEquals(c));
  });
});
