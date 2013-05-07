// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.exportTo('tracing.analysis', function() {
  function StubAnalysisResults() {
    this.tables = [];
  }
  StubAnalysisResults.prototype = {
    __proto__: Object.protoype,

    appendTable: function(parent, className) {
      var table = {
        className: className,
        rows: []
      };
      table.className = className;
      this.tables.push(table);
      return table;
    },

    appendTableHeader: function(table, label) {
      if (table.tableHeader)
        throw new Error('Only one summary header allowed.');
      table.tableHeader = label;
    },

    appendSummaryRow: function(table, label, opt_text) {
      table.rows.push({label: label,
        text: opt_text});
    },

    appendSpacingRow: function(table) {
      table.rows.push({spacing: true});
    },

    appendSummaryRowTime: function(table, label, time) {
      table.rows.push({label: label,
        time: time});
    },

    appendDataRow: function(table, label, duration, occurences,
                            details, selectionGenerator) {
      table.rows.push({label: label,
        duration: duration,
        occurences: occurences,
        details: details,
        selectionGenerator: selectionGenerator});
    }
  };

  return {
    StubAnalysisResults: StubAnalysisResults
  };
});
