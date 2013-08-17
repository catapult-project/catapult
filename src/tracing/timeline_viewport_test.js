// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.timeline_viewport');

base.unittest.testSuite('tracing.timeline_viewport', function() {
  test('memoization', function() {

    var vp = new tracing.TimelineViewport(document.createElement('div'));

    var slice = { guid: 1 };

    vp.modelTrackContainer = {
      addEventsToTrackMap: function(eventToTrackMap) {
        eventToTrackMap.addEvent(slice, 'track');
      },
      addEventListener: function() {}
    };

    assertUndefined(vp.trackForEvent(slice));
    vp.rebuildEventToTrackMap();

    assertEquals('track', vp.trackForEvent(slice));
  });
});
