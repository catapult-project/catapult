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
    __proto__: Parser.prototype,

    decodeFields: function(header, decoder) {
      if (header.version > 3)
        throw new Error('Incompatible Thread event version.');

      // Common fields to all Thread events.
      var processId = decoder.decodeUInt32();
      var threadId = decoder.decodeUInt32();

      // Extended fields.
      var stackBase;
      var stackLimit;
      var userStackBase;
      var userStackLimit;
      var affinity;
      var startAddr;
      var win32StartAddr;
      var tebBase;
      var subProcessTag;
      var basePriority;
      var pagePriority;
      var ioPriority;
      var threadFlags;
      var waitMode;

      if (header.version == 1) {
        // On version 1, only start events have extended information.
        if (header.opcode == kThreadStartOpcode ||
            header.opcode == kThreadDCStartOpcode) {
          stackBase = decoder.decodeUInteger(header.is64);
          stackLimit = decoder.decodeUInteger(header.is64);
          userStackBase = decoder.decodeUInteger(header.is64);
          userStackLimit = decoder.decodeUInteger(header.is64);
          startAddr = decoder.decodeUInteger(header.is64);
          win32StartAddr = decoder.decodeUInteger(header.is64);
          waitMode = decoder.decodeInt8();
          decoder.skip(3);
        }
      } else {
        stackBase = decoder.decodeUInteger(header.is64);
        stackLimit = decoder.decodeUInteger(header.is64);
        userStackBase = decoder.decodeUInteger(header.is64);
        userStackLimit = decoder.decodeUInteger(header.is64);

        // Version 2 produces a field named 'startAddr'.
        if (header.version == 2)
          startAddr = decoder.decodeUInteger(header.is64);
        else
          affinity = decoder.decodeUInteger(header.is64);

        win32StartAddr = decoder.decodeUInteger(header.is64);
        tebBase = decoder.decodeUInteger(header.is64);
        subProcessTag = decoder.decodeUInt32();

        if (header.version == 3) {
          basePriority = decoder.decodeUInt8();
          pagePriority = decoder.decodeUInt8();
          ioPriority = decoder.decodeUInt8();
          threadFlags = decoder.decodeUInt8();
        }
      }

      return {
        processId: processId,
        threadId: threadId,
        stackBase: stackBase,
        stackLimit: stackLimit,
        userStackBase: userStackBase,
        userStackLimit: userStackLimit,
        affinity: affinity,
        startAddr: startAddr,
        win32StartAddr: win32StartAddr,
        tebBase: tebBase,
        subProcessTag: subProcessTag,
        waitMode: waitMode,
        basePriority: basePriority,
        pagePriority: pagePriority,
        ioPriority: ioPriority,
        threadFlags: threadFlags
      };
    },

    decodeCSwitchFields: function(header, decoder) {
      if (header.version != 2)
        throw new Error('Incompatible Thread event version.');

      // Decode CSwitch payload.
      var newThreadId = decoder.decodeUInt32();
      var oldThreadId = decoder.decodeUInt32();
      var newThreadPriority = decoder.decodeInt8();
      var oldThreadPriority = decoder.decodeInt8();
      var previousCState = decoder.decodeUInt8();
      var spareByte = decoder.decodeInt8();
      var oldThreadWaitReason = decoder.decodeInt8();
      var oldThreadWaitMode = decoder.decodeInt8();
      var oldThreadState = decoder.decodeInt8();
      var oldThreadWaitIdealProcessor = decoder.decodeInt8();
      var newThreadWaitTime = decoder.decodeUInt32();
      var reserved = decoder.decodeUInt32();

      return {
        newThreadId: newThreadId,
        oldThreadId: oldThreadId,
        newThreadPriority: newThreadPriority,
        oldThreadPriority: oldThreadPriority,
        previousCState: previousCState,
        spareByte: spareByte,
        oldThreadWaitReason: oldThreadWaitReason,
        oldThreadWaitMode: oldThreadWaitMode,
        oldThreadState: oldThreadState,
        oldThreadWaitIdealProcessor: oldThreadWaitIdealProcessor,
        newThreadWaitTime: newThreadWaitTime,
        reserved: reserved
      };
    },

    decodeStart: function(header, decoder) {
      var fields = this.decodeFields(header, decoder);
      // TODO(etienneb): Update the TraceModel with |fields|..
      return true;
    },

    decodeEnd: function(header, decoder) {
      var fields = this.decodeFields(header, decoder);
      // TODO(etienneb): Update the TraceModel with |fields|.
      return true;
    },

    decodeDCStart: function(header, decoder) {
      var fields = this.decodeFields(header, decoder);
      // TODO(etienneb): Update the TraceModel with |fields|.
      return true;
    },

    decodeDCEnd: function(header, decoder) {
      var fields = this.decodeFields(header, decoder);
      // TODO(etienneb): Update the TraceModel with |fields|.
      return true;
    },

    decodeCSwitch: function(header, decoder) {
      var fields = this.decodeCSwitchFields(header, decoder);
      // TODO(etienneb): Update the TraceModel with |fields|.
      return true;
    }

  };

  Parser.registerSubtype(ThreadParser);

  return {
    ThreadParser: ThreadParser
  };
});
