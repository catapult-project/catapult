// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.exportTo('tracing.analysis', function() {
  function StubAnalysisResults() {
    this.headers = [];
    this.info = [];
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
      table.classList = [];
      table.classList.push(className);
      table.classList.add = function(className) {
        table.classList.push(className);
      };
      this.tables.push(table);
      return table;
    },

    appendHeader: function(label) {
      var header = {
        label: label
      };
      this.headers.push(header);
      return header;
    },

    appendInfo: function(label, value) {
      this.info.push({label: label, value: value});
    },

    appendDetailsRow: function(table, start, duration, selfTime, args,
                               selectionGenerator, cpuDuration) {
      table.rows.push({
        start: start,
        duration: duration,
        selfTime: selfTime,
        args: args,
        selectionGenerator: selectionGenerator,
        cpuDuration: cpuDuration});
    },

    appendHeadRow: function(table) {
      if (table.headerRow)
        throw new Error('Only one header row allowed.');
      table.headerRow = [];
      return table.headerRow;
    },

    appendTableCell: function(table, row, text) {
      row.push(text);
    },

    appendSpacingRow: function(table) {
      var row = {spacing: true};
      table.rows.push(row);
      return row;
    },

    appendInfoRow: function(table, label, opt_text) {
      var row = {label: label, text: opt_text};
      table.rows.push(row);
      return row;
    },

    appendInfoRowTime: function(table, label, time) {
      var row = {label: label, time: time};
      table.rows.push(row);
      return row;
    },

    appendDataRow: function(table, label, duration, cpuDuration, selfTime,
                            cpuSelfTime, occurences, percentage, details,
                            selectionGenerator) {
      var row = {
        label: label,
        duration: duration,
        cpuDuration: cpuDuration,
        selfTime: selfTime,
        cpuSelfTime: cpuSelfTime,
        occurences: occurences,
        percentage: percentage,
        details: details,
        selectionGenerator: selectionGenerator
      };
      table.rows.push(row);
      return row;
    }
  };

  return {
    StubAnalysisResults: StubAnalysisResults
  };
});
