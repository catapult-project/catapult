// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.event_target');
base.require('base.events');

base.unittest.testSuite('base.event_target', function() {
  test('eventTargetHelper', function() {
    var listenerCallCount = 0;
    function listener() { listenerCallCount++; }

    var div = document.createElement('div');
    base.EventTargetHelper.decorate(div);

    assertFalse(div.hasEventListener('foo'));

    div.addEventListener('foo', listener);
    assertTrue(div.hasEventListener('foo'));

    base.dispatchSimpleEvent(div, 'foo');
    assertEquals(1, listenerCallCount);

    div.removeEventListener('foo', listener);

    base.dispatchSimpleEvent(div, 'foo');
    assertEquals(1, listenerCallCount);

    assertFalse(div.hasEventListener('foo'));
  });
});
