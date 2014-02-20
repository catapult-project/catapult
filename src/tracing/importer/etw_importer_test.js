// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.importer.etw_importer');

tvcm.unittest.testSuite('tracing.importer.etw_importer_test', function() {

  test('canImport', function() {
    assertFalse(tracing.importer.EtwImporter.canImport('string'));
    assertFalse(tracing.importer.EtwImporter.canImport([]));

    // Must not parse an invalid name.
    var dummy = { name: 'dummy', content: [] };
    assertFalse(tracing.importer.EtwImporter.canImport(dummy));

    // Must parse  an empty valid trace.
    var valid = { name: 'ETW', content: [] };
    assertTrue(tracing.importer.EtwImporter.canImport(valid));
  });

  test('getModel', function() {
    var model = 'dummy';
    var events = [];
    var importer = new tracing.importer.EtwImporter(model, events);
    assertTrue(model === importer.model);
  });

  test('registerEventHandler', function() {
    // Create a dummy EtwImporter.
    var model = 'dummy';
    var events = ['events'];
    var importer = new tracing.importer.EtwImporter(model, events);
    var dummy_handler = function() {};

    // The handler must not exists.
    assertFalse(importer.getEventHandler('ABCDEF', 2));

    // Register an event handler for guid: ABCDEF and opcode: 2.
    importer.registerEventHandler('ABCDEF', 2, dummy_handler);

    // The handler exists now, must find it.
    assertTrue(importer.getEventHandler('ABCDEF', 2));

    // Must be able to manage an invalid handler.
    assertFalse(importer.getEventHandler('zzzzzz', 2));
  });

  test('parseEvent', function() {
    var model = 'dummy';
    var events = [];
    var importer = new tracing.importer.EtwImporter(model, events);
    var handler_called = false;
    var dummy_handler = function() { handler_called = true; return true; };

    // Register a valid handler.
    importer.registerEventHandler('aaaa', 42, dummy_handler);

    // Try to parse an invalid event with missing fields.
    var incomplet_event = { guid: 'aaaa', 'op': 42, 'ver': 0 };
    assertFalse(importer.parseEvent(incomplet_event));
    assertFalse(handler_called);

    // Try to parse a valid event.
    var valid_event = {
      guid: 'aaaa', 'op': 42, 'ver': 0, 'cpu': 0, 'ts': 0, 'payload': '0'
    };
    assertTrue(importer.parseEvent(valid_event));
    assertTrue(handler_called);
  });

});
