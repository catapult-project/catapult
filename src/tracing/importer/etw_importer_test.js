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
      guid: 'aaaa', 'op': 42, 'ver': 0, 'cpu': 0, 'ts': 0, 'payload': btoa('0')
    };
    assertTrue(importer.parseEvent(valid_event));
    assertTrue(handler_called);
  });

  test('decode', function() {
    var model = 'dummy';
    var events = [];
    var importer = new tracing.importer.EtwImporter(model, events);

    var decoder = importer.decoder_;

    decoder.reset('YQBiYw==');
    assertTrue(decoder.decodeInt32() == 0x63620061);

    // Decode unsigned numbers.
    decoder.reset('AQ==');
    assertTrue(decoder.decodeUInt8() == 0x01);

    decoder.reset('AQI=');
    assertTrue(decoder.decodeUInt16() == 0x0201);

    decoder.reset('AQIDBA==');
    assertTrue(decoder.decodeUInt32() == 0x04030201);

    decoder.reset('AQIDBAUGBwg=');
    assertTrue(decoder.decodeUInt64() == 0x0807060504030201);

    // Decode signed numbers.
    decoder.reset('AQ==');
    assertTrue(decoder.decodeInt8() == 0x01);

    decoder.reset('AQI=');
    assertTrue(decoder.decodeInt16() == 0x0201);

    decoder.reset('AQIDBA==');
    assertTrue(decoder.decodeInt32() == 0x04030201);

    decoder.reset('AQIDBAUGBwg=');
    assertTrue(decoder.decodeInt64() == 0x0807060504030201);

    // Last value before being a signed number.
    decoder.reset('fw==');
    assertTrue(decoder.decodeInt8() == 127);

    // Decode negative numbers.
    decoder.reset('1g==');
    assertTrue(decoder.decodeInt8() == -42);

    decoder.reset('gA==');
    assertTrue(decoder.decodeInt8() == -128);

    decoder.reset('hYI=');
    assertTrue(decoder.decodeInt16() == -32123);

    decoder.reset('hYL//w==');
    assertTrue(decoder.decodeInt32() == -32123);

    decoder.reset('Lv1ptv////8=');
    assertTrue(decoder.decodeInt32() == -1234567890);

    // Decode number with zero (nul) in the middle of the string.
    decoder.reset('YQBiYw==');
    assertTrue(decoder.decodeInt32() == 0x63620061);
  });

});
