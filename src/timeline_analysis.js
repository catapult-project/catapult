// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineView visualizes TRACE_EVENT events using the
 * tracing.Timeline component and adds in selection summary and control buttons.
 */
cr.define('tracing', function() {
  function tsRound(ts) {
    return Math.round(ts * 1000.0) / 1000.0;
  }

  /**
   * Creates and appends a DOM node of type |tagName| to |parent|. Optionally,
   * sets the new node's text to |opt_text|. Returns the newly created node.
   */
  function appendElement(parent, tagName, opt_text) {
    var n = parent.ownerDocument.createElement(tagName);
    parent.appendChild(n);
    if (opt_text != undefined)
      n.textContent = opt_text;
    return n;
  }

  /**
   * Adds |tagName| to |parent| with className |classname|.  Returns
   * the newly created node.
   */
  function appendElementWithClass(parent, tagName, classname) {
    var n = appendElement(parent, tagName);
    n.className = classname;
    return n;
  }

  /**
   * Adds |text| to |parent|.
   */
  function appendText(parent, text) {
    var textNode = parent.ownerDocument.createTextNode(text);
    parent.appendChild(textNode);
    return textNode;
  }

  /**
   * Adds a table header to |row| with |text| and className
   * |table|.className-header.  Returns the newly created node.
   */
  function appendTableHeader(table, row, text) {
    var th = appendElement(row, 'th', text);
    th.className = table.className + '-header';
    return th;
  }

  /**
   * Adds table cell number |cellnum| to |row| with |text| and
   * className |table|.className-col-|cellnum|.  Returns the newly
   * created node.
   */
  function appendTableCell(table, row, cellnum, text) {
    var td = appendElement(row, 'td', text);
    td.className = table.className + '-col-' + cellnum;
    return td;
  }

  /**
   * Creates and appends a row to |table| with a left-aligned |label]
   * header that spans all columns.  Returns the newly created nodes.
   */
  function appendSummaryHeader(table, label) {
    var row = appendElement(table, 'tr');
    var th = appendTableHeader(table, row, label);
    return row;
  }

  /**
   * Creates and appends a row to |table| with a left-aligned |label]
   * in the first column and an optional |opt_text| value in the second
   * column.  Returns the newly created nodes.
   */
  function appendSummaryRow(table, label, opt_text) {
    var row = appendElement(table, 'tr');
    var td = appendTableCell(table, row, 0, label);
    if (opt_text) {
      var td = appendTableCell(table, row, 1, opt_text);
    }
    return row;
  }

  /**
   * Creates and appends a row to |table| with a left-aligned |label]
   * in the first column and a millisecvond |time| value in the second
   * column.  Returns the newly created nodes.
   */
  function appendSummaryRowTime(table, label, time) {
    return appendSummaryRow(table, label, tsRound(time) + ' ms');
  }

  /**
   * Creates and appends a row to |table| that summarizes one or more slices.
   * The row has a left-aligned |label] in the first column, the |duration|
   * of the data in the second, the number of |occurrences| in the third.
   * Returns the newly created nodes.
   */
  function appendSliceRow(table, label, duration, occurences) {
      var row = appendElement(table, 'tr');
      var td = appendTableCell(table, row, 0, label);
      var td = appendTableCell(table, row, 1, tsRound(duration) + ' ms');
      var td = appendTableCell(table, row, 2,
          String(occurences) + ' occurences');
      return row;
  }

  /**
   * Converts the selection to a tabular summary display and appends
   * the newly created elements to |parent|.  Returns the new elements.
   */
  function createSummaryElementForSelection(parent, selection) {
    var sliceHits = selection.getSliceHits();
    var counterSampleHits = selection.getCounterSampleHits();

    if (sliceHits.length == 1) {
      var slice = sliceHits[0].slice;

      var table = appendElementWithClass(parent, 'table', 'timeline-slice');

      appendSummaryHeader(table, 'Selected item:');

      appendSummaryRow(table, 'Title', slice.title);
      appendSummaryRowTime(table, 'Start', slice.start);
      appendSummaryRowTime(table, 'Duration', slice.duration);
      if (slice.durationInUserTime)
        appendSummaryRowTime(table, 'Duration (U)', slice.durationInUserTime);

      var n = 0;
      for (var argName in slice.args) {
        n += 1;
      }
      if (n > 0) {
        appendSummaryRow(table, 'Args');
        for (var argName in slice.args) {
          var argVal = slice.args[argName];
          // TODO(sleffler) use span instead?
          appendSummaryRow(table, ' ' + argName, argVal);
        }
      }
    } else if (sliceHits.length > 1) {
      var tsLo = sliceHits.range.min;
      var tsHi = sliceHits.range.max;

      // compute total sliceHits duration
      var titles = sliceHits.map(function(i) { return i.slice.title; });

      var slicesByTitle = {};
      for (var i = 0; i < sliceHits.length; i++) {
        var slice = sliceHits[i].slice;
        if (!slicesByTitle[slice.title])
          slicesByTitle[slice.title] = {
            slices: []
          };
        slicesByTitle[slice.title].slices.push(slice);
      }

      var table = appendElementWithClass(parent, 'table', 'timeline-slices');

      appendSummaryHeader(table, 'Slices:');

      var totalDuration = 0;
      for (var sliceGroupTitle in slicesByTitle) {
        var sliceGroup = slicesByTitle[sliceGroupTitle];
        var duration = 0;
        for (i = 0; i < sliceGroup.slices.length; i++)
          duration += sliceGroup.slices[i].duration;
        totalDuration += duration;

        appendSliceRow(table, sliceGroupTitle, duration,
            sliceGroup.slices.length);
      }

      appendSliceRow(table, '*Totals', totalDuration, sliceHits.length);

      appendElement(table, 'p');  // TODO(sleffler) proper vertical space?
      appendSummaryRowTime(table, 'Selection start', tsLo);
      appendSummaryRowTime(table, 'Selection extent', tsHi - tsLo);
    }

    if (counterSampleHits.length == 1) {
      var hit = counterSampleHits[0];
      var ctr = hit.counter;
      var sampleIndex = hit.sampleIndex;
      var values = [];
      for (var i = 0; i < ctr.numSeries; ++i)
        values.push(ctr.samples[ctr.numSeries * sampleIndex + i]);

      var table = appendElementWithClass(parent, 'table', 'timeline-counter');

      appendSummaryHeader(table, 'Selected counter:');

      appendSummaryRow(table, 'Title', ctr.name);
      appendSummaryRowTime(table, 'Timestamp', ctr.timestamps[sampleIndex]);
      if (ctr.numSeries > 1)
        appendSummaryRow(table, 'Values', values.join('\n'));
      else
        appendSummaryRow(table, 'Value', values.join('\n'));
    } else if (counterSampleHits.length > 1 && sliceHits.length == 0) {
      appendText(parent, 'Analysis of multiple counters is not yet' +
          'implemented. Pick a single counter.');
    }
  }

  var TimelineAnalysisView = cr.ui.define('div');

  TimelineAnalysisView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'timeline-analysis';
    },

    set selection(selection) {
      this.textContent = '';
      createSummaryElementForSelection(this, selection);
    }
  };

  return {
    TimelineAnalysisView: TimelineAnalysisView,
  };
});
