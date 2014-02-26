// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Base class for Windows ETW event parsers.
 *
 * The ETW trace event importer depends on subclasses of
 * Parser to parse event data.  Each subclass corresponds
 * to a group of trace events; e.g. Thread and Process implements
 * decoding of scheduling events.  Parser subclasses must
 * call Parser.registerSubtype to arrange to be instantiated
 * and their constructor must register their event handlers with the
 * importer.  For example,
 *
 * var Parser = tracing.importer.etw.Parser;
 *
 * function ThreadParser(importer) {
 *   Parser.call(this, importer);
 *
 *   importer.registerEventHandler(guid, kThreadStartOpcode,
 *       ThreadParser.prototype.decodeStart.bind(this));
 *   importer.registerEventHandler(guid, kThreadEndOpcode,
 *       ThreadParser.prototype.decodeEnd.bind(this));
 * }
 *
 * Parser.registerSubtype(ThreadParser);
 *
 * When a registered event is found, the associated event handler is invoked:
 *
 *   decodeStart: function(header, decoder) {
 *     [...]
 *     return true;
 *   },
 *
 * If the routine returns false the caller will generate an import error
 * saying there was a problem parsing it.  Handlers can also emit import
 * messages using this.importer.model.importWarning.  If this is done in lieu of
 * the generic import error it may be desirable for the handler to return
 * true.
 *
 */
tvcm.exportTo('tracing.importer.etw', function() {

  var subtypeConstructors = [];

  /**
   * Registers a subclass that will help parse Windows ETW events.
   * The importer will call createParsers (below) before importing
   * data so each subclass can register its handlers.
   *
   * @param {Function} subtypeConstructor The subtype's constructor function.
   */
  Parser.registerSubtype = function(subtypeConstructor) {
    subtypeConstructors.push(subtypeConstructor);
  };

  Parser.getSubtypeConstructors = function() {
    return subtypeConstructors;
  };

  /**
   * Parses Windows ETW events.
   * @constructor
   */
  function Parser(importer) {
    this.importer = importer;
    this.model = importer.model;
  }

  Parser.prototype = {
    __proto__: Object.prototype
  };

  return {
    Parser: Parser
  };

});
