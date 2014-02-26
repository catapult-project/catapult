// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Parses processes events in the Windows event trace format.
 */
tvcm.require('tracing.importer.etw.parser');

tvcm.exportTo('tracing.importer.etw', function() {

  var Parser = tracing.importer.etw.Parser;

  // Constants for Process events.
  var guid = '3D6FA8D0-FE05-11D0-9DDA-00C04FD7BA7C';
  var kProcessStartOpcode = 1;
  var kProcessEndOpcode = 2;
  var kProcessDCStartOpcode = 3;
  var kProcessDCEndOpcode = 4;
  var kProcessDefunctOpcode = 39;

  /**
   * Parses Windows process trace events.
   * @constructor
   */
  function ProcessParser(importer) {
    Parser.call(this, importer);

    // Register handlers.
    importer.registerEventHandler(guid, kProcessStartOpcode,
        ProcessParser.prototype.decodeStart.bind(this));
    importer.registerEventHandler(guid, kProcessEndOpcode,
        ProcessParser.prototype.decodeEnd.bind(this));
    importer.registerEventHandler(guid, kProcessDCStartOpcode,
        ProcessParser.prototype.decodeDCStart.bind(this));
    importer.registerEventHandler(guid, kProcessDCEndOpcode,
        ProcessParser.prototype.decodeDCEnd.bind(this));
    importer.registerEventHandler(guid, kProcessDefunctOpcode,
        ProcessParser.prototype.decodeDefunct.bind(this));
  }

  ProcessParser.prototype = {

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

    decodeDefunct: function(header, decoder) {
      // TODO(etienneb): decode payload.
      return true;
    }

  };

  Parser.registerSubtype(ProcessParser);

  return {
    ProcessParser: ProcessParser
  };
});
