// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.analyze_counters');
base.require('tracing.analysis.analyze_slices');
base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  /**
   * Analyzes the selection, outputting the analysis results into the provided
   * results object.
   *
   * @param {AnalysisResults} results Where the analysis is placed.
   * @param {Selection} selection What to analyze.
   */
  function analyzeSelection(results, selection) {
    analyzeEventsByType(results, selection.getEventsOrganizedByType());
  }

  function analyzeEventsByType(results, eventsByType) {
    var sliceEvents = eventsByType.slices;
    var counterSampleEvents = eventsByType.counterSamples;
    var instantEvents = eventsByType.instantEvents;
    var sampleEvents = eventsByType.samples;
    var objectEvents = new tracing.Selection();
    objectEvents.addSelection(eventsByType.objectSnapshots);
    objectEvents.addSelection(eventsByType.objectInstances);

    if (sliceEvents.length == 1) {
      tracing.analysis.analyzeSingleSlice(results, sliceEvents[0], 'Slice');
    } else if (sliceEvents.length > 1) {
      tracing.analysis.analyzeMultipleSlices(results, sliceEvents, 'Slices');
    }

    if (instantEvents.length == 1) {
      tracing.analysis.analyzeSingleSlice(results, instantEvents[0],
                                          'Instant Event');
    } else if (instantEvents.length > 1) {
      tracing.analysis.analyzeMultipleSlices(results, instantEvents,
                                             'Instant Events');
    }

    if (sampleEvents.length == 1) {
      tracing.analysis.analyzeSingleSlice(results, sampleEvents[0],
                                          'Sample Event');
    } else if (sampleEvents.length > 1) {
      tracing.analysis.analyzeMultipleSlices(results, sampleEvents,
                                             'Sample Events');
    }

    if (counterSampleEvents.length != 0)
      tracing.analysis.analyzeCounterSamples(results, counterSampleEvents);

    if (objectEvents.length)
      analyzeObjectEvents(results, objectEvents);
  }

  /**
   * Extremely simplistic analysis of objects. Mainly exists to provide
   * click-through to the main object's analysis view.
   */
  function analyzeObjectEvents(results, objectEvents) {
    objectEvents = base.asArray(objectEvents).sort(
        base.Range.compareByMinTimes);

    results.appendHeader('Selected Objects:');
    var table = results.appendTable('analysis-object-sample-table', 2);

    objectEvents.forEach(function(event) {
      var row = results.appendBodyRow(table);
      var ts;
      var objectText;
      var selectionGenerator;
      if (event instanceof tracing.trace_model.ObjectSnapshot) {
        var objectSnapshot = event;
        ts = tracing.analysis.tsRound(objectSnapshot.ts);
        objectText = objectSnapshot.objectInstance.typeName + ' ' +
            objectSnapshot.objectInstance.id;
        selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.push(objectSnapshot);
          return selection;
        };
      } else {
        var objectInstance = event;

        var deletionTs = objectInstance.deletionTs == Number.MAX_VALUE ?
            '' : tracing.analysis.tsRound(objectInstance.deletionTs);
        ts = tracing.analysis.tsRound(objectInstance.creationTs) +
            '-' + deletionTs;

        objectText = objectInstance.typeName + ' ' +
            objectInstance.id;

        selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.push(objectInstance);
          return selection;
        };
      }

      results.appendTableCell(table, row, ts);
      var linkContainer = results.appendTableCell(table, row, '');
      linkContainer.appendChild(
          results.createSelectionChangingLink(objectText, selectionGenerator));
    });
  }

  return {
    analyzeSelection: analyzeSelection,
    analyzeEventsByType: analyzeEventsByType
  };
});
