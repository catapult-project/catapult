// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.analysis.analysis_results');

tvcm.require('tracing.analysis.util');
tvcm.require('tracing.analysis.analysis_link');
tvcm.require('tracing.analysis.generic_object_view');
tvcm.require('tvcm.ui');

tvcm.exportTo('tracing.analysis', function() {
  var AnalysisResults = tvcm.ui.define('div');

  AnalysisResults.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'analysis-results';
    },

    get requiresTallView() {
      return false;
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

    appendTableCell_: function(table, row, cellnum, text, opt_warning) {
      var td = this.appendElement_(row, 'td', text);
      td.className = table.className + '-col-' + cellnum;
      if (opt_warning) {
        var span = document.createElement('span');
        span.textContent = ' ' + String.fromCharCode(9888);
        span.title = opt_warning;
        td.appendChild(span);
      }
      return td;
    },

    /**
     * Creates and append a table cell at the end of the given row.
     */
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
     * Creates and appends a section header element.
     */
    appendHeader: function(label) {
      var header = this.appendElement_(this, 'span', label);
      header.className = 'analysis-header';
      return header;
    },

    /**
     * Creates and appends a info element of the format "<b>label</b>value".
     */
    appendInfo: function(label, value) {
      var div = this.appendElement_(this, 'div');
      div.label = this.appendElement_(div, 'b', label);
      div.value = this.appendElement_(div, 'span', value);
      return div;
    },

    /**
     * Adds a table with the given className.
     *
     * @return {HTMLTableElement} The newly created table.
     */
    appendTable: function(className, numColumns) {
      var table = this.appendElement_(this, 'table');
      table.className = className + ' analysis-table';
      table.numColumns = numColumns;
      return table;
    },

    /**
     * Creates and appends a |tr| in |thead|, if |thead| does not exist, create
     * it as well.
     */
    appendHeadRow: function(table) {
      if (table.headerRow)
        throw new Error('Only one header row allowed.');
      if (table.tbody || table.tfoot)
        throw new Error(
            'Cannot add a header row after data rows have been added.');
      table.headerRow = this.appendElement_(
                                  this.appendElement_(table, 'thead'), 'tr');
      table.headerRow.className = 'analysis-table-header';
      return table.headerRow;
    },

    /**
     * Creates and appends a |tr| in |tbody|, if |tbody| does not exist, create
     * it as well.
     */
    appendBodyRow: function(table) {
      if (table.tfoot)
        throw new Error(
            'Cannot add a tbody row after footer rows have been added.');
      if (!table.tbody)
        table.tbody = this.appendElement_(table, 'tbody');
      var row = this.appendElement_(table.tbody, 'tr');
      if (table.headerRow)
        row.className = 'analysis-table-row';
      else
        row.className = 'analysis-table-row-inverted';
      return row;
    },

    /**
     * Creates and appends a |tr| in |tfoot|, if |tfoot| does not exist, create
     * it as well.
     */
    appendFootRow: function(table) {
      if (!table.tfoot) {
        table.tfoot = this.appendElement_(table, 'tfoot');
        table.tfoot.rowsClassName = (
            (table.headerRow ? 1 : 0) +
            (table.tbody ? table.tbody.rows.length : 0)) % 2 ?
                'analysis-table-row' : 'analysis-table-row-inverted';
      }

      var row = this.appendElement_(table.tfoot, 'tr');
      row.className = table.tfoot.rowsClassName;
      return row;
    },

    /**
     * Adds a spacing row to spread out results.
     */
    appendSpacingRow: function(table, opt_inFoot) {
      if (table.tfoot || opt_inFoot)
        var row = this.appendFootRow(table);
      else
        var row = this.appendBodyRow(table);
      for (var i = 0; i < table.numColumns; i++)
        this.appendTableCell_(table, row, i, ' ');
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label] in the
     * first column and an optional |opt_value| in the second column.
     */
    appendInfoRow: function(table, label, opt_value, opt_inFoot) {
      if (table.tfoot || opt_inFoot)
        var row = this.appendFootRow(table);
      else
        var row = this.appendBodyRow(table);
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
     * Creates and appends a row to |table| with a left-aligned |label] in the
     * first column and a millisecond |time| value in the second column.
     */
    appendInfoRowTime: function(table, label, time, opt_inFoot, opt_warning) {
      if (table.tfoot || opt_inFoot)
        var row = this.appendFootRow(table);
      else
        var row = this.appendBodyRow(table);
      this.appendTableCell_(table, row, 0, label);
      this.appendTableCell_(
          table, row, 1, tracing.analysis.tsRound(time) + ' ms', opt_warning);
    },

    /**
     * Creates and appends a row to |table| that summarizes a single slice or a
     * single counter. The row has a left-aligned |start| in the first column,
     * the |duration| of the data in the second, the number of |occurrences| in
     * the third.
     *
     * @param {object=} opt_statistics May be undefined, or an object which
     *          contains calculated staistics containing min/max/avg for slices,
     *          or min/max/avg/start/end for counters.
     */
    appendDetailsRow: function(table, start, duration, selfTime, args,
        opt_selectionGenerator, opt_cpuDuration) {
      var row = this.appendBodyRow(table);

      if (opt_selectionGenerator) {
        var labelEl = this.appendTableCell(table, row,
                                           tracing.analysis.tsRound(start));
        labelEl.textContent = '';
        labelEl.appendChild(this.createSelectionChangingLink(
                                    tracing.analysis.tsRound(start),
                                    opt_selectionGenerator, ''));
      } else {
        this.appendTableCell(table, row, tracing.analysis.tsRound(start));
      }

      if (duration !== null)
        this.appendTableCell(table, row, tracing.analysis.tsRound(duration));

      if (opt_cpuDuration)
        this.appendTableCell(table, row,
                             opt_cpuDuration != '' ?
                             tracing.analysis.tsRound(opt_cpuDuration) :
                             '');

      if (selfTime !== null)
        this.appendTableCell(table, row, tracing.analysis.tsRound(selfTime));

      var argsCell = this.appendTableCell(table, row, '');
      var n = 0;
      for (var argName in args) {
        n += 1;
      }

      if (n > 0) {
        for (var argName in args) {
          var argVal = args[argName];
          var objectView = new tracing.analysis.GenericObjectView();
          objectView.object = argVal;
          var argsRow = this.appendElement_(
              this.appendElement_(argsCell, 'table'), 'tr');
          this.appendElement_(argsRow, 'td', argName + ':');
          this.appendElement_(argsRow, 'td').appendChild(objectView);
        }
      }
    },

    /**
     * Creates and appends a row to |table| that summarizes one or more slices,
     * or one or more counters. The row has a left-aligned |label| in the first
     * column, the |duration| of the data in the second, the number of
     * |occurrences| in the third.
     *
     * @param {object=} opt_statistics May be undefined, or an object which
     *          contains calculated staistics containing min/max/avg for slices,
     *          or min/max/avg/start/end for counters.
     */
    appendDataRow: function(table, label, opt_duration, opt_cpuDuration,
                            opt_selfTime, opt_cpuSelfTime, opt_occurences,
                            opt_percentage, opt_statistics,
                            opt_selectionGenerator, opt_inFoot) {

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

      if (table.tfoot || opt_inFoot)
        var row = this.appendFootRow(table);
      else
        var row = this.appendBodyRow(table);

      var cellNum = 0;
      if (!opt_selectionGenerator) {
        this.appendTableCellWithTooltip_(table, row, cellNum, label, tooltip);
      } else {
        var labelEl = this.appendTableCellWithTooltip_(
            table, row, cellNum, label, tooltip);
        if (labelEl) {
          labelEl.textContent = '';
          labelEl.appendChild(
              this.createSelectionChangingLink(label, opt_selectionGenerator,
                                               tooltip));
        }
      }
      cellNum++;

      if (opt_duration !== null) {
        if (opt_duration) {
          if (opt_duration instanceof Array) {
            this.appendTableCellWithTooltip_(table, row, cellNum,
                '[' + opt_duration.join(', ') + ']', tooltip);
          } else {
            this.appendTableCellWithTooltip_(table, row, cellNum,
                tracing.analysis.tsRound(opt_duration), tooltip);
          }
        } else {
          this.appendTableCell_(table, row, cellNum, '');
        }
        cellNum++;
      }

      if (opt_cpuDuration !== null) {
        if (opt_cpuDuration != '') {
          this.appendTableCellWithTooltip_(table, row, cellNum,
              tracing.analysis.tsRound(opt_cpuDuration), tooltip);
        } else {
          this.appendTableCell_(table, row, cellNum, '');
        }
        cellNum++;
      }

      if (opt_selfTime !== null) {
        if (opt_selfTime) {
          this.appendTableCellWithTooltip_(table, row, cellNum,
              tracing.analysis.tsRound(opt_selfTime), tooltip);
        } else {
          this.appendTableCell_(table, row, cellNum, '');
        }
        cellNum++;
      }

      if (opt_cpuSelfTime !== null) {
        if (opt_cpuSelfTime) {
          this.appendTableCellWithTooltip_(table, row, cellNum,
              tracing.analysis.tsRound(opt_cpuSelfTime), tooltip);
        } else {
          this.appendTableCell_(table, row, cellNum, '');
        }
        cellNum++;
      }

      if (opt_percentage !== null) {
        if (opt_percentage) {
          this.appendTableCellWithTooltip_(table, row, cellNum,
                                           opt_percentage, tooltip);
        } else {
          this.appendTableCell_(table, row, cellNum, '');
        }
        cellNum++;
      }

      if (opt_occurences) {
        this.appendTableCellWithTooltip_(table, row, cellNum,
            String(opt_occurences), tooltip);
      } else {
        this.appendTableCell_(table, row, cellNum, '');
      }
      cellNum++;
    }
  };
  return {
    AnalysisResults: AnalysisResults
  };
});
