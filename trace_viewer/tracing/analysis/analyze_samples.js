// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.analysis.analyze_slices');

tvcm.require('tracing.analysis.util');
tvcm.require('tvcm.ui');
tvcm.require('tvcm.ui.sortable_table');

tvcm.exportTo('tracing.analysis', function() {

  function analyzeSingleSampleEvent(results, sample, type) {
    results.appendHeader('Selected ' + type + ':');
    var table = results.appendTable('analysis-slice-table', 2);

    results.appendInfoRow(table, 'Title', sample.title);
    results.appendInfoRowTime(table, 'Sample Time', sample.start);
    results.appendInfoRow(table,
                          'Stack Trace',
                          sample.getUserFriendlyStackTrace());
  }

  function analyzeSingleTypeSampleEvents_(results, sliceGroup) {
    results.appendInfo('Title: ', sliceGroup[0].title);
    results.appendInfo('Category: ', sliceGroup[0].category);

    var table = results.appendTable('analysis-slice-table', 2);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Start');
    results.appendTableCell(table, row, 'Args');

    var numSlices = 0;
    tvcm.iterItems(sliceGroup, function(title, slice) {
      numSlices++;
      results.appendDetailsRow(table, slice.start, null, null, slice.args,
          function() {
            return new tracing.Selection([slice]);
          });
    });
    if (numSlices > 1)
      tvcm.ui.SortableTable.decorate(table);
  }

  function analyzeMultipleSampleEvents(results, slices, type) {
    var tsLo = slices.bounds.min;
    var tsHi = slices.bounds.max;

    var numTitles = 0;
    var sliceGroups = {};
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (sliceGroups[slice.leafStackFrame.title] === undefined) {
        sliceGroups[slice.leafStackFrame.title] = [];
        numTitles++;
      }
      sliceGroups[slice.leafStackFrame.title].push(slices[i]);
    }

    // Sort slice groups in the descending order of occurrences.
    // We treat the occurrence of the 'Sleeping' event as 0.
    var sortedSlices = [];
    var totalOccurrence = 0;
    for (var title in sliceGroups) {
      var occurrence;
      if (title === 'Sleeping') {
        occurrence = 0;
      } else {
        occurrence = sliceGroups[title].length;
        totalOccurrence += occurrence;
      }
      sortedSlices.push({
        title: title, sliceGroup: sliceGroups[title],
        occurrence: occurrence});
    }
    sortedSlices = sortedSlices.sort(function(a, b) {
      return b.occurrence - a.occurrence;
    });

    results.appendHeader(type + ':');
    var table = results.appendTable('analysis-slice-table', 3);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Name');
    results.appendTableCell(table, row, 'Percentage');
    results.appendTableCell(table, row, 'Occurrences');

    for (var i = 0; i < sortedSlices.length; i++) {
      var title = sortedSlices[i].title;
      var sliceGroup = sortedSlices[i].sliceGroup;
      results.appendDataRow(table, title, null, null,
          null, null, sliceGroup.length,
          (title === 'Sleeping' ? '-' :
           tracing.analysis.tsRound(
               sliceGroup.length / totalOccurrence * 100) + '%'),
          null,
          function() {
            return new tracing.Selection(sliceGroup);
          });

      // The whole selection is a single type so list out the information
      // for each sub slice.
      if (numTitles === 1)
        analyzeSingleTypeSampleEvents_(results, sliceGroup);
    }

    // Only one row so we already know the totals.
    if (numTitles !== 1) {
      results.appendDataRow(table, 'Totals', null, null, null, null,
                            slices.length, '100%', null, null, true);
      results.appendSpacingRow(table, true);
      tvcm.ui.SortableTable.decorate(table);
    }

    results.appendInfoRowTime(table, 'Selection start', tsLo, true);
    results.appendInfoRowTime(table, 'Selection extent', tsHi - tsLo, true);
  }

  return {
    analyzeMultipleSampleEvents: analyzeMultipleSampleEvents,
    analyzeSingleSampleEvent: analyzeSingleSampleEvent
  };
});
