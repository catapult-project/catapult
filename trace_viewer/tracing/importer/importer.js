// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Base class for trace data importers.
 */

tvcm.exportTo('tracing.importer', function() {

  function Importer() {
  }

  Importer.prototype = {
    __proto__: Object.prototype,

    /**
     * Called by the Model to extract one or more subtraces from the event data.
     */
    extractSubtraces: function() {
      return [];
    },

    /**
     * Called to import events into the Model.
     */
    importEvents: function() {
    },

    /**
     * Called to import sample data into the Model.
     */
    importSampleData: function() {
    },

    /**
     * Called by the Model after all other importers have imported their
     * events.
     */
    finalizeImport: function() {
    },

    /**
     * Called by the Model to join references between objects, after final
     * model bounds have been computed.
     */
    joinRefs: function() {
    }
  };

  return {
    Importer: Importer
  };
});
