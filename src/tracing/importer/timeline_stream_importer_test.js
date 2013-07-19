// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.events');
base.require('tracing.test_utils');
base.require('tracing.importer.timeline_stream_importer');

base.unittest.testSuite('tracing.importer.timeline_stream_importer', function() { // @suppress longLineCheck
  var FakeWebSocket = function() {
    base.EventTarget.call(this);
    this.sendHook_ = undefined;
    this.messages_ = [];
    this.connected_ = false;
  };

  FakeWebSocket.prototype = {
    __proto__: base.EventTarget.prototype,

    set connected(connected) {
      if (this.connected_ == connected)
        return;
      this.connected_ = connected;
      if (this.connected_)
        base.dispatchSimpleEvent(this, 'connect');
      else
        base.dispatchSimpleEvent(this, 'disconnect');
    },

    get readyState() {
      if (this.connected_)
        return WebSocket.OPEN;
      return WebSocket.CLOSED;
    },

    pushMessage: function(msg) {
      this.messages_.push(JSON.stringify(msg));
    },

    get numPendingMessages() {
      return this.messages_.length;
    },

    dispatchAllPendingMessages: function() {
      var messages = this.messages_.splice(0, this.messages_.length);
      for (var i = 0; i < messages.length; i++)
        this.dispatchEvent({type: 'message', data: messages[i]});
    },

    /**
     * @param {function(message)} hook A function to call when send is
     called on the socket.
     */
    set sendHook(hook) {
      this.sendHook_ = hook;
    },

    send: function(message) {
      if (this.sendHook_)
        this.sendHook_(message);
    },

    set onopen(handler) {
      this.addEventListener('open', handler);
    },

    set onclose(handler) {
      this.addEventListener('close', handler);
    },

    set onerror(handler) {
      this.addEventListener('error', handler);
    },

    set onmessage(handler) {
      this.addEventListener('message', handler);
    }
  };

  test('importBasic', function() {
    var model = new tracing.TraceModel();
    var importer = new tracing.importer.TimelineStreamImporter(model);

    assertFalse(importer.paused);
    assertFalse(importer.connected);

    var socket = new FakeWebSocket();
    importer.connect(socket);

    socket.connected = true;
    assertTrue(importer.connected);

    socket.pushMessage({
      cmd: 'ptd',
      pid: 1,
      td: { n: 3,
        s: [
          {s: 10, e: 11, l: 'alligator'},
          {s: 14, e: 15, l: 'bandicoot'},
          {s: 17, e: 18, l: 'cheetah'}
        ]
      }
    });
    socket.dispatchAllPendingMessages();

    assertNotUndefined(model.processes[1]);
    assertNotUndefined(model.processes[1].threads[3]);
    var t3 = model.processes[1].threads[3];
    assertEquals(3, t3.sliceGroup.length);

    assertEquals(model.bounds.min, 10);
    assertEquals(model.bounds.max, 18);
  });

  test('pause', function() {
    var model = new tracing.TraceModel();
    var importer = new tracing.importer.TimelineStreamImporter(model);

    assertFalse(importer.paused);

    var socket = new FakeWebSocket();
    importer.connect(socket);
    socket.connected = true;

    var didSend = false;
    socket.sendHook = function(message) {
      var data = JSON.parse(message);
      didSend = true;
      assertEquals('pause', data['cmd']);
    };
    importer.pause();
    assertTrue(didSend);
    assertTrue(importer.paused);

    didSend = false;
    socket.sendHook = function(message) {
      var data = JSON.parse(message);
      didSend = true;
      assertEquals('resume', data['cmd']);
    };
    importer.resume();
    assertTrue(didSend);
    assertFalse(importer.paused);
  });

  test('counters', function() {
    var model = new tracing.TraceModel();
    var importer = new tracing.importer.TimelineStreamImporter(model);

    assertFalse(importer.paused);
    assertFalse(importer.connected);

    var socket = new FakeWebSocket();
    importer.connect(socket);

    socket.connected = true;
    assertTrue(importer.connected);

    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes'],
        sc: [4],
        c: [
          {
            t: 2,
            v: [16]
          },
          {
            t: 16,
            v: [32]
          }
        ]
      }
    });

    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes'],
        sc: [4],
        c: [
          {
            t: 32,
            v: [48]
          },
          {
            t: 48,
            v: [64]
          },
          {
            t: 64,
            v: [16]
          }
        ]
      }
    });

    socket.dispatchAllPendingMessages();

    assertNotUndefined(model.processes[1]);
    assertNotUndefined(model.processes[1].counters['streamed.Allocator']);

    var counter = model.processes[1].counters['streamed.Allocator'];
    assertNotUndefined(counter.series);

    assertEquals(1, counter.series.length);
    assertEquals(5, counter.series[0].length);

    assertEquals(48, counter.series[0].getSample(2).value);
    assertEquals(64, counter.timestamps[4]);

    assertEquals(model.bounds.min, 2);
    assertEquals(model.bounds.max, 64);
  });

  test('counterImportErrors', function() {
    var model = new tracing.TraceModel();
    var importer = new tracing.importer.TimelineStreamImporter(model);

    assertFalse(importer.paused);
    assertFalse(importer.connected);

    var socket = new FakeWebSocket();
    importer.connect(socket);

    socket.connected = true;
    assertTrue(importer.connected);

    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes', 'Nibbles', 'Bits'],
        sc: [4, 3, 2],
        c: [
          {
            t: 2,
            v: [16, 12, 2]
          },
          {
            t: 16,
            v: [32, 3, 4]
          }
        ]
      }
    });

    // Test for name change import error
    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes', 'NotNibbles', 'Bits'],
        sc: [4, 3, 2],
        c: [
          {
            t: 18,
            v: [16, 12, 2]
          },
          {
            t: 24,
            v: [32, 3, 4]
          }
        ]
      }
    });

    socket.dispatchAllPendingMessages();

    assertNotUndefined(model.processes[1]);
    assertEquals(model.importErrors.length, 1);
    // test for series number change
    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes', 'Bits'],
        sc: [4, 3],
        c: [
          {
            t: 26,
            v: [16, 12]
          },
          {
            t: 32,
            v: [32, 3]
          }
        ]
      }
    });

    socket.dispatchAllPendingMessages();
    assertEquals(model.importErrors.length, 2);

    // test for sn.length != sc.length
    socket.pushMessage({
      cmd: 'pcd',
      pid: 1,
      cd: {
        n: 'Allocator',
        sn: ['Bytes', 'Nibbles', 'Bits'],
        sc: [4, 3, 2, 5],
        c: [
          {
            t: 2,
            v: [16, 12, 2]
          },
          {
            t: 16,
            v: [32, 3, 4]
          }
        ]
      }
    });


    socket.dispatchAllPendingMessages();
    assertEquals(model.importErrors.length, 3);
  });
});
