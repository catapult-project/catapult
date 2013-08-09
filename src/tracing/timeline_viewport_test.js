// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.timeline_viewport');

base.unittest.testSuite('tracing.timeline_viewport', function() {
  test('memoization', function() {
    var vp = new tracing.TimelineViewport(document.createElement('div'));

    var slice = { guid: 1 };
    assertUndefined(vp.trackForSlice(slice));

    vp.sliceMemoization(slice, 'track');
    assertEquals('track', vp.trackForSlice(slice));

    vp.clearSliceMemoization();
    assertUndefined(vp.trackForSlice(slice));
  });
});
