// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.key_event_manager');

base.unittest.testSuite('base.key_event_manager', function() {
  var KeyEventManager = base.KeyEventManager;

  function withElementAttachedToChild(element, callback) {
    document.body.appendChild(element);
    try {
      callback();
    } finally {
      document.body.removeChild(element);
    }
  }


  test('simpleDispatch', function() {
    var kem = KeyEventManager.instance;
    var div = document.createElement('div');

    var fireCount = 0;
    kem.addListener('keydown', function(e) {
      fireCount++;
    }, div);

    // Send an event while its attached to the document.
    withElementAttachedToChild(div, function() {
      var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
      assertTrue(ret == undefined);
      assertEquals(1, fireCount);
    });
    fireCount = 0;

    // Send an event while it is detached.
    var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
    assertTrue(ret == undefined);
    assertEquals(0, fireCount);
  });

  test('preventDefault', function() {
    var kem = KeyEventManager.instance;
    var div = document.createElement('div');

    var fireCount = 0;
    kem.addListener('keydown', function(e) {
      fireCount++;
      e.preventDefault();
    }, div);

    withElementAttachedToChild(div, function() {
      var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
      assertTrue(ret == false);
      assertEquals(1, fireCount);
    });

  });

  test('stopPropagation', function() {
    var kem = KeyEventManager.instance;
    var div1 = document.createElement('div');
    var div2 = document.createElement('div');

    var didFire = false;
    kem.addListener('keydown', function(e) {
      e.stopPropagation();
    }, div1);
    kem.addListener('keydown', function(e) {
      throw new Error('Should never get called');
    }, div2);

    withElementAttachedToChild(div1, function() {
      withElementAttachedToChild(div2, function() {
        var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
        assertTrue(ret == undefined);
      });
    });
  });

  test('removeListener', function() {
    var kem = KeyEventManager.instance;
    var div = document.createElement('div');

    var handlerFired = false;
    function handler(e) {
      handlerFired = true;
    }
    kem.addListener('keydown', handler, div);
    kem.removeListener('keydown', handler, div);
    assertEquals(div.className, '');

    withElementAttachedToChild(div, function() {
      var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
      assertFalse(handlerFired);
    });
  });

  test('removeOneListener', function() {
    var kem = KeyEventManager.instance;
    var div = document.createElement('div');

    var handlerAFired = false;
    function handlerA(e) {
      handlerAFired = true;
    }
    var handlerBFired = false;
    function handlerB(e) {
      handlerBFired = true;
    }
    kem.addListener('keydown', handlerA, div);
    kem.addListener('keydown', handlerB, div);
    kem.removeListener('keydown', handlerA, div);
    assertTrue(div.classList.contains('key-event-manager-target'));

    withElementAttachedToChild(div, function() {
      var ret = kem.dispatchFakeEvent('keydown', {keyCode: 73});
      assertFalse(handlerAFired);
      assertTrue(handlerBFired);
    });
  });


});
