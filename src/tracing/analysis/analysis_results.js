// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.analysis.analysis_results');

base.require('tracing.analysis.util');
base.require('tracing.analysis.analysis_link');
base.require('tracing.analysis.generic_object_view');
base.require('ui');

base.exportTo('tracing.analysis', function() {
  var AnalysisResults = ui.define('div');

  AnalysisResults.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'analysis-results';
    },

    clear: function() {
      this.textContent = '';
    },

    createSelectionChangingLink: function(text, selectionGenerator,
                                          opt_tooltip) {
      var el = this.ownerDocument.createElement('a');
      tracing.analysis.AnalysisLink.decorate(el);
      el.textContent = text;
      el.selectionGenerator = selectionGenerator;
      if (opt_tooltip)
        el.title = opt_tooltip;
      return el;
    },

    appendElement_: function(parent, tagName, opt_text) {
      var n = parent.ownerDocument.createElement(tagName);
      parent.appendChild(n);
      if (opt_text != undefined)
        n.textContent = opt_text;
      return n;
    },

    appendText_: function(parent, text) {
      var textElement = parent.ownerDocument.createTextNode(text);
      parent.appendChild(textNode);
      return textNode;
    },

    appendTableCell_: function(table, row, cellnum, text) {
      var td = this.appendElement_(row, 'td', text);
      td.className = table.className + '-col-' + cellnum;
      return td;
    },

    appendTableCell: function(table, row, text) {
      return this.appendTableCell_(table, row, row.children.length, text);
    },

    appendTableCellWithTooltip_: function(table, row, cellnum, text, tooltip) {
      if (tooltip) {
        var td = this.appendElement_(row, 'td');
        td.className = table.className + '-col-' + cellnum;
        var span = this.appendElement_(td, 'span', text);
        span.className = 'tooltip';
        span.title = tooltip;
        return td;
      } else {
        this.appendTableCell_(table, row, cellnum, text);
      }
    },

    /**
     * Adds a table with the given className.
     * @return {HTMLTableElement} The newly created table.
     */
    appendTable: function(className, numColumns) {
      var table = this.appendElement_(this, 'table');
      table.headerRow = this.appendElement_(table, 'tr');
      table.className = className + ' analysis-table';
      table.numColumns = numColumns;
      return table;
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * header that spans all columns.
     */
    appendTableHeader: function(table, label) {
      var th = this.appendElement_(table.headerRow, 'th', label);
      th.className = 'analysis-table-header';
    },

    appendTableRow: function(table) {
      return this.appendElement_(table, 'tr');
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * in the first column and an optional |opt_value| in the second
     * column.
     */
    appendSummaryRow: function(table, label, opt_value) {
      var row = this.appendElement_(table, 'tr');
      row.className = 'analysis-table-row';

      this.appendTableCell_(table, row, 0, label);

      if (opt_value !== undefined) {
        var objectView = new tracing.analysis.GenericObjectView();
        objectView.object = opt_value;
        objectView.classList.add('analysis-table-col-1');
        objectView.style.display = 'table-cell';
        row.appendChild(objectView);
      } else {
        this.appendTableCell_(table, row, 1, '');
      }
      for (var i = 2; i < table.numColumns; i++)
        this.appendTableCell_(table, row, i, '');
    },

    /**
     * Adds a spacing row to spread out results.
     */
    appendSpacingRow: function(table) {
      var row = this.appendElement_(table, 'tr');
      row.className = 'analysis-table-row';
      for (var i = 0; i < table.numColumns; i++)
        this.appendTableCell_(table, row, i, ' ');
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * in the first column and a millisecvond |time| value in the second
     * column.
     */
    appendSummaryRowTime: function(table, label, time) {
      this.appendSummaryRow(table, label,
                            tracing.analysis.tsRound(time) + ' ms');
    },

    /**
     * Creates and appends a row to |table| that summarizes one or more slices,
     * or one or more counters.
     * The row has a left-aligned |label| in the first column, the |duration|
     * of the data in the second, the number of |occurrences| in the third.
     * @param {object=} opt_statistics May be undefined, or an object which
     * contains calculated staistics containing min/max/avg for slices, or
     * min/max/avg/start/end for counters.
     */
    appendDataRow: function(
        table, label, opt_duration, opt_occurences,
        opt_statistics, opt_selectionGenerator) {

      var tooltip = undefined;
      if (opt_statistics) {
        tooltip = 'Min Duration:\u0009' +
                  tracing.analysis.tsRound(opt_statistics.min) +
                  ' ms \u000DMax Duration:\u0009' +
                  tracing.analysis.tsRound(opt_statistics.max) +
                  ' ms \u000DAvg Duration:\u0009' +
                  tracing.analysis.tsRound(opt_statistics.avg) +
                  ' ms (\u03C3 = ' +
                  tracing.analysis.tsRound(opt_statistics.avg_stddev) + ')';

        if (opt_statistics.start) {
          tooltip += '\u000DStart Time:\u0009' +
              tracing.analysis.tsRound(opt_statistics.start) + ' ms';
        }
        if (opt_statistics.end) {
          tooltip += '\u000DEnd Time:\u0009' +
              tracing.analysis.tsRound(opt_statistics.end) + ' ms';
        }
        if (opt_statistics.frequency && opt_statistics.frequency_stddev) {
          tooltip += '\u000DFrequency:\u0009' +
              tracing.analysis.tsRound(opt_statistics.frequency) +
              ' occurrences/s (\u03C3 = ' +
              tracing.analysis.tsRound(opt_statistics.frequency_stddev) + ')';
        }
      }

      var row = this.appendElement_(table, 'tr');
      row.className = 'analysis-table-row';

      if (!opt_selectionGenerator) {
        this.appendTableCellWithTooltip_(table, row, 0, label, tooltip);
      } else {
        var labelEl = this.appendTableCellWithTooltip_(
            table, row, 0, label, tooltip);
        labelEl.textContent = '';
        labelEl.appendChild(
            this.createSelectionChangingLink(label, opt_selectionGenerator,
            tooltip));
      }

      if (opt_duration !== undefined) {
        if (opt_duration instanceof Array) {
          this.appendTableCellWithTooltip_(table, row, 1,
              '[' + opt_duration.join(', ') + ']', tooltip);
        } else {
          this.appendTableCellWithTooltip_(table, row, 1,
              tracing.analysis.tsRound(opt_duration) + ' ms', tooltip);
        }
      } else {
        this.appendTableCell_(table, row, 1, '');
      }

      if (opt_occurences !== undefined) {
        this.appendTableCellWithTooltip_(table, row, 2,
            String(opt_occurences) + ' occurrences', tooltip);

      } else {
        this.appendTableCell_(table, row, 2, '');
      }
    }
  };
  return {
    AnalysisResults: AnalysisResults
  };
});
