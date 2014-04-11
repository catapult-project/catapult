// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.analysis.analyze_slices');

tvcm.require('tracing.analysis.util');
tvcm.require('tvcm.ui');
tvcm.require('tvcm.ui.sortable_table');

tvcm.exportTo('tracing.analysis', function() {

  function analyzeSingleSlice(results, slice, type) {
    results.appendHeader('Selected ' + type + ':');
    var table = results.appendTable('analysis-slice-table', 2);

    if (slice.title)
      results.appendInfoRow(table, 'Title', slice.title);

    if (slice.category)
      results.appendInfoRow(table, 'Category', slice.category);

    results.appendInfoRowTime(table, 'Start', slice.start);
    results.appendInfoRowTime(table, 'Duration', slice.duration);

    if (slice.threadDuration)
      results.appendInfoRowTime(table, 'ThreadDuration', slice.threadDuration);

    if (slice.selfTime)
      results.appendInfoRowTime(table, 'SelfTime', slice.selfTime);

    if (slice.threadSelfTime) {
      var warning;
      if (slice.threadSelfTime > slice.selfTime) {
        warning =
            'Note that ThreadSelfTime is larger than SelfTime. ' +
            'This is a known limitation of this system, which occurs ' +
            'due to several subslices, rounding issues, and inprecise ' +
            'time at which we get thread- and real-time.';
      }
      results.appendInfoRowTime(table, 'ThreadSelfTime', slice.threadSelfTime,
                                false, warning);
    }

    if (slice.durationInUserTime) {
      results.appendInfoRowTime(table, 'Duration (U)',
                                slice.durationInUserTime);
    }

    var n = 0;
    for (var argName in slice.args) {
      n += 1;
    }
    if (n > 0) {
      results.appendInfoRow(table, 'Args');
      for (var argName in slice.args) {
        var argVal = slice.args[argName];
        // TODO(sleffler) use span instead?
        results.appendInfoRow(table, ' ' + argName, argVal);
      }
    }
  }

  function analyzeSingleTypeSlices_(results, sliceGroup, hasThreadDuration) {
    results.appendInfo('Title: ', sliceGroup[0].title);
    results.appendInfo('Category: ', sliceGroup[0].category);

    var table = results.appendTable('analysis-slice-table',
                                    4 + hasThreadDuration);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Start');
    results.appendTableCell(table, row, 'Duration (ms)');
    if (hasThreadDuration)
      results.appendTableCell(table, row, 'ThreadDuration (ms)');
    results.appendTableCell(table, row, 'SelfTime (ms)');
    results.appendTableCell(table, row, 'Args');

    var numSlices = 0;
    tvcm.iterItems(sliceGroup, function(title, slice) {
      numSlices++;
      results.appendDetailsRow(table, slice.start, slice.duration,
          slice.selfTime ? slice.selfTime : slice.duration, slice.args,
          function() {
            return new tracing.Selection([slice]);
          }, slice.threadDuration);
    });
    if (numSlices > 1)
      tvcm.ui.SortableTable.decorate(table);
  }

  function analyzeMultipleSlices(results, slices, type) {
    var tsLo = slices.bounds.min;
    var tsHi = slices.bounds.max;

    var numTitles = 0;
    var sliceGroups = {};
    var hasThreadDuration = false;

    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (sliceGroups[slice.title] === undefined) {
        sliceGroups[slice.title] = [];
        numTitles++;
      }

      if (slice.threadDuration)
        hasThreadDuration = true;

      var sliceGroup = sliceGroups[slice.title];
      sliceGroup.push(slices[i]);
    }

    results.appendHeader(type + ':');
    var table = results.appendTable('analysis-slice-table',
                                    4 + hasThreadDuration);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Name');
    results.appendTableCell(table, row, 'Duration (ms)');
    if (hasThreadDuration)
      results.appendTableCell(table, row, 'ThreadDuration (ms)');
    results.appendTableCell(table, row, 'SelfTime (ms)');
    if (hasThreadDuration)
      results.appendTableCell(table, row, 'ThreadSelfTime (ms)');
    results.appendTableCell(table, row, 'Occurrences');

    var totalDuration = 0;
    var totalthreadDuration = 0;
    var totalSelfTime = 0;
    var totalThreadSelfTime = 0;
    tvcm.iterItems(sliceGroups, function(sliceGroupTitle, sliceGroup) {
      var duration = 0;
      var threadDuration = 0;
      var selfTime = 0;
      var threadSelfTime = 0;
      var avg = 0;
      var startOfFirstOccurrence = Number.MAX_VALUE;
      var startOfLastOccurrence = -Number.MAX_VALUE;
      var min = Number.MAX_VALUE;
      var max = -Number.MAX_VALUE;
      for (var i = 0; i < sliceGroup.length; i++) {
        var slice = sliceGroup[i];
        duration += slice.duration;
        if (slice.threadDuration) {
          threadDuration += slice.threadDuration;
          threadSelfTime += slice.threadSelfTime ? slice.threadSelfTime :
                                                   slice.threadDuration;
        }
        selfTime += slice.selfTime ? slice.selfTime : slice.duration;
        startOfFirstOccurrence = Math.min(slice.start, startOfFirstOccurrence);
        startOfLastOccurrence = Math.max(slice.start, startOfLastOccurrence);
        min = Math.min(slice.duration, min);
        max = Math.max(slice.duration, max);
      }

      totalDuration += duration;
      totalthreadDuration += threadDuration;
      totalSelfTime += selfTime;
      totalThreadSelfTime += threadSelfTime;

      if (sliceGroup.length == 0)
        avg = 0;
      avg = duration / sliceGroup.length;

      var statistics = {
        min: min,
        max: max,
        avg: avg,
        avg_stddev: undefined,
        frequency: undefined,
        frequency_stddev: undefined
      };

      // Compute the stddev of the slice durations.
      var sumOfSquaredDistancesToMean = 0;
      for (var i = 0; i < sliceGroup.length; i++) {
        var signedDistance = statistics.avg - sliceGroup[i].duration;
        sumOfSquaredDistancesToMean += signedDistance * signedDistance;
      }

      statistics.avg_stddev =
          Math.sqrt(sumOfSquaredDistancesToMean / (sliceGroup.length - 1));

      // We require at least 3 samples to compute the stddev.
      var elapsed = startOfLastOccurrence - startOfFirstOccurrence;
      if (sliceGroup.length > 2 && elapsed > 0) {
        var numDistances = sliceGroup.length - 1;
        statistics.frequency = (1000 * numDistances) / elapsed;

        // Compute the stddev.
        sumOfSquaredDistancesToMean = 0;
        for (var i = 1; i < sliceGroup.length; i++) {
          var currentFrequency =
              1000 / (sliceGroup[i].start - sliceGroup[i - 1].start);
          var signedDistance = statistics.frequency - currentFrequency;
          sumOfSquaredDistancesToMean += signedDistance * signedDistance;
        }

        statistics.frequency_stddev =
            Math.sqrt(sumOfSquaredDistancesToMean / (numDistances - 1));
      }
      results.appendDataRow(table, sliceGroupTitle, duration,
                            hasThreadDuration ? (threadDuration > 0 ?
                                threadDuration : '') : null,
                            selfTime,
                            hasThreadDuration ? (threadSelfTime > 0 ?
                                threadSelfTime : '') : null,
                            sliceGroup.length, null, statistics, function() {
                              return new tracing.Selection(sliceGroup);
                            });

      // The whole selection is a single type so list out the information
      // for each sub slice.
      if (numTitles === 1)
        analyzeSingleTypeSlices_(results, sliceGroup, hasThreadDuration);
    });

    // Only one row so we already know the totals.
    if (numTitles !== 1) {
      results.appendDataRow(table, 'Totals', totalDuration,
                            hasThreadDuration ? totalthreadDuration : null,
                            totalSelfTime, totalThreadSelfTime, slices.length,
                            null, null, null, true);
      results.appendSpacingRow(table, true);
      tvcm.ui.SortableTable.decorate(table);
    }

    results.appendInfoRowTime(table, 'Selection start', tsLo, true);
    results.appendInfoRowTime(table, 'Selection extent', tsHi - tsLo, true);
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
    analyzeSingleSlice: analyzeSingleSlice,
    analyzeMultipleSlices: analyzeMultipleSlices,
    analyzeMultipleSampleEvents: analyzeMultipleSampleEvents
  };
});
