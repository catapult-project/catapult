base.require('base.event_target');

'use strict';

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
