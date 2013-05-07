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
    analyzeHitsByType(results, selection.getHitsOrganizedByType());
  }

  function analyzeHitsByType(results, hitsByType) {
    var sliceHits = hitsByType.slices;
    var counterSampleHits = hitsByType.counterSamples;
    var objectHits = new tracing.Selection();
    objectHits.addSelection(hitsByType.objectSnapshots);
    objectHits.addSelection(hitsByType.objectInstances);

    if (sliceHits.length == 1) {
      tracing.analysis.analyzeSingleSliceHit(results, sliceHits[0]);
    } else if (sliceHits.length > 1) {
      tracing.analysis.analyzeMultipleSliceHits(results, sliceHits);
    }

    if (counterSampleHits.length == 1) {
      tracing.analysis.analyzeSingleCounterSampleHit(
          results, counterSampleHits[0]);
    } else if (counterSampleHits.length > 1) {
      tracing.analysis.analyzeMultipleCounterSampleHits(
          results, counterSampleHits);
    }

    if (objectHits.length)
      analyzeObjectHits(results, objectHits);
  }

  /**
   * Extremely simplistic analysis of objects. Mainly exists to provide
   * click-through to the main object's analysis view.
   */
  function analyzeObjectHits(results, objectHits) {
    objectHits = base.asArray(objectHits).sort(base.Range.compareByMinTimes);

    var table = results.appendTable('analysis-object-sample-table', 2);
    results.appendTableHeader(table, 'Selected Objects:');

    objectHits.forEach(function(hit) {
      var row = results.appendTableRow(table);
      var ts;
      var objectText;
      var selectionGenerator;
      if (hit instanceof tracing.SelectionObjectSnapshotHit) {
        var objectSnapshot = hit.objectSnapshot;
        ts = tracing.analysis.tsRound(objectSnapshot.ts);
        objectText = objectSnapshot.objectInstance.typeName + ' ' +
            objectSnapshot.objectInstance.id;
        selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.addObjectSnapshot(hit.track, objectSnapshot);
          return selection;
        };
      } else {
        var objectInstance = hit.objectInstance;

        var deletionTs = objectInstance.deletionTs == Number.MAX_VALUE ?
            '' : tracing.analysis.tsRound(objectInstance.deletionTs);
        ts = tracing.analysis.tsRound(objectInstance.creationTs) +
            '-' + deletionTs;

        objectText = objectInstance.typeName + ' ' +
            objectInstance.id;

        selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.addObjectInstance(hit.track, objectInstance);
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
    analyzeHitsByType: analyzeHitsByType
  };
});
