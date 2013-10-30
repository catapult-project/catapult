// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('tracing.analysis.analyze_slices');

base.require('tracing.analysis.util');
base.require('ui');
base.require('ui.sortable_table');

base.exportTo('tracing.analysis', function() {

  function analyzeSingleSlice(results, slice, type) {
    results.appendHeader('Selected ' + type + ':');
    var table = results.appendTable('analysis-slice-table', 2);

    results.appendInfoRow(table, 'Title', slice.title);

    if (slice.category)
      results.appendInfoRow(table, 'Category', slice.category);

    results.appendInfoRowTime(table, 'Start', slice.start);
    results.appendInfoRowTime(table, 'Duration', slice.duration);

    if (slice.threadTime)
      results.appendInfoRowTime(table, 'ThreadTime', slice.threadTime);

    if (slice.selfTime)
      results.appendInfoRowTime(table, 'SelfTime', slice.selfTime);

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

  function analyzeSingleTypeSlices_(results, sliceGroup, hasThreadTime) {
    results.appendInfo('Title: ', sliceGroup[0].title);
    results.appendInfo('Category: ', sliceGroup[0].category);

    var table = results.appendTable('analysis-slice-table', 4 + hasThreadTime);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Start');
    results.appendTableCell(table, row, 'Duration (ms)');
    if (hasThreadTime)
      results.appendTableCell(table, row, 'ThreadTime (ms)');
    results.appendTableCell(table, row, 'SelfTime (ms)');
    results.appendTableCell(table, row, 'Args');

    var numSlices = 0;
    base.iterItems(sliceGroup, function(title, slice) {
      numSlices++;
      results.appendDetailsRow(table, slice.start, slice.duration,
          slice.selfTime ? slice.selfTime : slice.duration, slice.args,
          function() {
            return new tracing.Selection([slice]);
          }, slice.threadTime);
    });
    if (numSlices > 1)
      ui.SortableTable.decorate(table);
  }

  function analyzeMultipleSlices(results, slices, type) {
    var tsLo = slices.bounds.min;
    var tsHi = slices.bounds.max;

    var numTitles = 0;
    var slicesByTitle = {};
    var hasThreadTime = false;

    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (slicesByTitle[slice.title] === undefined) {
        slicesByTitle[slice.title] = [];
        numTitles++;
      }

      if (slice.threadTime)
        hasThreadTime = true;

      var sliceGroup = slicesByTitle[slice.title];
      sliceGroup.push(slices[i]);
    }

    results.appendHeader(type + ':');
    var table = results.appendTable('analysis-slice-table', 4 + hasThreadTime);
    var row = results.appendHeadRow(table);
    results.appendTableCell(table, row, 'Name');
    results.appendTableCell(table, row, 'Duration (ms)');
    if (hasThreadTime)
      results.appendTableCell(table, row, 'ThreadTime (ms)');
    results.appendTableCell(table, row, 'SelfTime (ms)');
    results.appendTableCell(table, row, 'Occurrences');

    var totalDuration = 0;
    var totalThreadTime = 0;
    var totalSelfTime = 0;
    base.iterItems(slicesByTitle, function(sliceGroupTitle, sliceGroup) {
      var duration = 0;
      var threadTime = 0;
      var selfTime = 0;
      var avg = 0;
      var startOfFirstOccurrence = Number.MAX_VALUE;
      var startOfLastOccurrence = -Number.MAX_VALUE;
      var min = Number.MAX_VALUE;
      var max = -Number.MAX_VALUE;
      for (var i = 0; i < sliceGroup.length; i++) {
        var slice = sliceGroup[i];
        duration += slice.duration;
        if (slice.threadTime)
          threadTime += slice.threadTime;
        selfTime += slice.selfTime ? slice.selfTime : slice.duration;
        startOfFirstOccurrence = Math.min(slice.start, startOfFirstOccurrence);
        startOfLastOccurrence = Math.max(slice.start, startOfLastOccurrence);
        min = Math.min(slice.duration, min);
        max = Math.max(slice.duration, max);
      }

      totalDuration += duration;
      totalThreadTime += threadTime;
      totalSelfTime += selfTime;

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
                            hasThreadTime ? (threadTime > 0 ?
                                threadTime : '') : null,
                            selfTime, sliceGroup.length, statistics,
                            function() {
                              return new tracing.Selection(sliceGroup);
                            });

      // The whole selection is a single type so list out the information
      // for each sub slice.
      if (numTitles === 1)
        analyzeSingleTypeSlices_(results, sliceGroup, hasThreadTime);
    });

    // Only one row so we already know the totals.
    if (numTitles !== 1) {
      results.appendDataRow(table, 'Totals', totalDuration,
                            hasThreadTime ? totalThreadTime : null,
                            totalSelfTime, slices.length, null, null, true);
      results.appendSpacingRow(table, true);
      ui.SortableTable.decorate(table);
    }

    results.appendInfoRowTime(table, 'Selection start', tsLo, true);
    results.appendInfoRowTime(table, 'Selection extent', tsHi - tsLo, true);
  }

  return {
    analyzeSingleSlice: analyzeSingleSlice,
    analyzeMultipleSlices: analyzeMultipleSlices
  };
});
