// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses threads events in the Windows event trace format.
 */
tvcm.require('tracing.importer.etw.parser');

tvcm.exportTo('tracing.importer.etw', function() {

  var Parser = tracing.importer.etw.Parser;

  // Constants for Thread events.
  var guid = '3D6FA8D1-FE05-11D0-9DDA-00C04FD7BA7C';
  var kThreadStartOpcode = 1;
  var kThreadEndOpcode = 2;
  var kThreadDCStartOpcode = 3;
  var kThreadDCEndOpcode = 4;
  var kThreadCSwitchOpcode = 36;

  /**
   * Parses Windows threads trace events.
   * @constructor
   */
  function ThreadParser(importer) {
    Parser.call(this, importer);

    // Register handlers.
    importer.registerEventHandler(guid, kThreadStartOpcode,
        ThreadParser.prototype.decodeStart.bind(this));
    importer.registerEventHandler(guid, kThreadEndOpcode,
        ThreadParser.prototype.decodeEnd.bind(this));
    importer.registerEventHandler(guid, kThreadDCStartOpcode,
        ThreadParser.prototype.decodeDCStart.bind(this));
    importer.registerEventHandler(guid, kThreadDCEndOpcode,
        ThreadParser.prototype.decodeDCEnd.bind(this));
    importer.registerEventHandler(guid, kThreadCSwitchOpcode,
        ThreadParser.prototype.decodeCSwitch.bind(this));
  }

  ThreadParser.prototype = {

    decodeStart: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    },

    decodeEnd: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    },

    decodeDCStart: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    },

    decodeDCEnd: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    },

    decodeCSwitch: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    }

  };

  Parser.registerSubtype(ThreadParser);

  return {
    ThreadParser: ThreadParser
  };
});
