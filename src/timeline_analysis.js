// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineView visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
base.defineModule('timeline_analysis')
    .dependsOn('ui')
    .stylesheet('timeline_analysis')
    .exportsTo('tracing', function() {

  var AnalysisResults = base.ui.define('div');

  AnalysisResults.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
    },

    tsRound_: function(ts) {
      return Math.round(ts * 1000.0) / 1000.0;
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

    /**
     * Adds a table with the given className.
     * @return The newly created table.
     */
    appendTable: function(className, numColumns) {
      var table = this.appendElement_(this, 'table');
      table.className = className + ' timeline-analysis-table';
      table.numColumns = numColumns;
      return table;
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * header that spans all columns.
     */
    appendTableHeader: function(table, label) {
      var row = this.appendElement_(table, 'tr');

      var th = this.appendElement_(row, 'th', label);
      th.className = 'timeline-analysis-table-header';
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * in the first column and an optional |opt_text| value in the second
     * column.
     */
    appendSummaryRow: function(table, label, opt_text) {
      var row = this.appendElement_(table, 'tr');
      row.className = 'timeline-analysis-table-row';

      this.appendTableCell_(table, row, 0, label);
      if (opt_text) {
        this.appendTableCell_(table, row, 1, opt_text);
        for (var i = 2; i < table.numColumns; i++)
          this.appendTableCell_(table, row, i, "");
      } else {
        for (var i = 1; i < table.numColumns; i++)
          this.appendTableCell_(table, row, 1, "");
      }
    },

    /**
     * Adds a spacing row to spread out results.
     */
    appendSpacingRow: function(table) {
      var row = this.appendElement_(table, 'tr');
      row.className = 'timeline-analysis-table-row';
      for (var i = 0; i < table.numColumns; i++)
        this.appendTableCell_(table, row, i, " ");
    },

    /**
     * Creates and appends a row to |table| with a left-aligned |label]
     * in the first column and a millisecvond |time| value in the second
     * column.
     */
    appendSummaryRowTime: function(table, label, time) {
      this.appendSummaryRow(table, label, this.tsRound_(time) + ' ms');
    },

    /**
     * Creates and appends a row to |table| that summarizes one or more slices.
     * The row has a left-aligned |label] in the first column, the |duration|
     * of the data in the second, the number of |occurrences| in the third.
     * @param details May be undefined, or an object with contain min/max/avg.
     */
    appendSliceRow: function(table, label, duration, occurences, opt_statistics) {
      var row = this.appendElement_(table, 'tr');
      row.className = 'timeline-analysis-table-row';
      this.appendTableCell_(table, row, 0, label);
      this.appendTableCell_(table, row, 1, this.tsRound_(duration) + ' ms');
      this.appendTableCell_(
          table, row, 2, String(occurences) + ' occurences');
      if (opt_statistics) {
        this.appendTableCell_(table, row, 3, 'min:' + this.tsRound_(opt_statistics.min));
        this.appendTableCell_(table, row, 4, 'max:' + this.tsRound_(opt_statistics.max));
        this.appendTableCell_(table, row, 5, 'avg:' + this.tsRound_(opt_statistics.avg));
      }
    },
  };

  /**
   * Analyzes the selection, outputting the analysis results into the provided results object.
   *
   * @param results Where the analysis is placed. Should be an AnalysisResults object or something
   * with compatible methods.
   *
   * @param selection The TimelineSelection to analyze.
   */
  function analyzeSelection(results, selection) {

    var sliceHits = selection.getSliceHits();
    var counterSampleHits = selection.getCounterSampleHits();

    if (sliceHits.length == 1) {
      var slice = sliceHits[0].slice;
      var table = results.appendTable('timeline-analysis-slice-table', 2);

      results.appendTableHeader(table, 'Selected item:');
      results.appendSummaryRow(table, 'Title', slice.title);
      results.appendSummaryRowTime(table, 'Start', slice.start);
      results.appendSummaryRowTime(table, 'Duration', slice.duration);

      if (slice.durationInUserTime)
        results.appendSummaryRowTime(table, 'Duration (U)', slice.durationInUserTime);

      var n = 0;
      for (var argName in slice.args) {
        n += 1;
      }
      if (n > 0) {
        results.appendSummaryRow(table, 'Args');
        for (var argName in slice.args) {
          var argVal = slice.args[argName];
          // TODO(sleffler) use span instead?
          results.appendSummaryRow(table, ' ' + argName, argVal);
        }
      }
    } else if (sliceHits.length > 1) {
      var tsLo = sliceHits.range.min;
      var tsHi = sliceHits.range.max;

      // compute total sliceHits duration
      var titles = sliceHits.map(function(i) { return i.slice.title; });

      var numTitles = 0;
      var slicesByTitle = {};
      for (var i = 0; i < sliceHits.length; i++) {
        var slice = sliceHits[i].slice;
        if (!slicesByTitle[slice.title]) {
          slicesByTitle[slice.title] = {
            slices: []
          };
          numTitles++;
        }
        slicesByTitle[slice.title].slices.push(slice);
      }

      var table;
      if (numTitles == 1)
        table = results.appendTable('timeline-analysis-slices-table', 4);
      else
        table = results.appendTable('timeline-analysis-slices-table', 3);
      results.appendTableHeader(table, 'Slices:');

      var totalDuration = 0;

      // This will output the min, max, and average if there is only one title
      for (var sliceGroupTitle in slicesByTitle) {
        var sliceGroup = slicesByTitle[sliceGroupTitle];
        var duration = 0;
        var avg = 0;
        var min = Number.MAX_VALUE;
        var max = Number.MIN_VALUE;
        for (var i = 0; i < sliceGroup.slices.length; i++) {
          duration += sliceGroup.slices[i].duration;
          min = Math.min(sliceGroup.slices[i].duration, min);
          max = Math.max(sliceGroup.slices[i].duration, max);
        }

        totalDuration += duration;

        if (sliceGroup.slices.length == 0)
          avg = 0;
        avg = duration / sliceGroup.slices.length;

        var details = undefined;
        if (numTitles == 1)
          details = {min: min,
                     max: max,
                     avg: avg};
        results.appendSliceRow(table, sliceGroupTitle, duration,
                               sliceGroup.slices.length, details);
      }
      results.appendSliceRow(table, '*Totals', totalDuration, sliceHits.length);
      results.appendSpacingRow(table);
      results.appendSummaryRowTime(table, 'Selection start', tsLo);
      results.appendSummaryRowTime(table, 'Selection extent', tsHi - tsLo);
    }

    if (counterSampleHits.length == 1) {
      var hit = counterSampleHits[0];
      var ctr = hit.counter;
      var sampleIndex = hit.sampleIndex;
      var values = [];
      for (var i = 0; i < ctr.numSeries; ++i)
        values.push(ctr.samples[ctr.numSeries * sampleIndex + i]);

      var table = results.appendTable('timeline-analysis-counter-table', 2);

      results.appendTableHeader(table, 'Selected counter:');
      results.appendSummaryRow(table, 'Title', ctr.name);
      results.appendSummaryRowTime(table, 'Timestamp', ctr.timestamps[sampleIndex]);
      if (ctr.numSeries > 1)
        results.appendSummaryRow(table, 'Values', values.join('\n'));
      else
        results.appendSummaryRow(table, 'Value', values.join('\n'));

    } else if (counterSampleHits.length > 1 && sliceHits.length == 0) {
      var table = results.appendTable('timeline-counter', 1);
      results.appendTableHeader(table, 'Multiple selected counters not supported.');
    }
  }

  var TimelineAnalysisView = base.ui.define('div');

  TimelineAnalysisView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'timeline-analysis';
    },

    set selection(selection) {
      this.textContent = '';
      var results = new AnalysisResults();
      analyzeSelection(results, selection);
      this.appendChild(results);
    }
  };

  return {
    TimelineAnalysisView: TimelineAnalysisView,
    analyzeSelection_: analyzeSelection,
  };
});
