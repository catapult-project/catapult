// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.event_target');
tvcm.require('tvcm.events');

tvcm.unittest.testSuite('tvcm.event_target_test', function() {
  test('eventTargetHelper', function() {
    var listenerCallCount = 0;
    function listener() { listenerCallCount++; }

    var div = document.createElement('div');
    tvcm.EventTargetHelper.decorate(div);

    assertFalse(div.hasEventListener('foo'));

    div.addEventListener('foo', listener);
    assertTrue(div.hasEventListener('foo'));

    tvcm.dispatchSimpleEvent(div, 'foo');
    assertEquals(1, listenerCallCount);

    div.removeEventListener('foo', listener);

    tvcm.dispatchSimpleEvent(div, 'foo');
    assertEquals(1, listenerCallCount);

    assertFalse(div.hasEventListener('foo'));
  });
});
