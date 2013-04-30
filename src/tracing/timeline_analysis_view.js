// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Displays an analysis of the selection.
 */
base.requireStylesheet('tracing.timeline_analysis_view');

base.require('tracing.analysis.selection_analysis');
base.require('tracing.analysis.analysis_results');
base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing', function() {

  var RequestSelectionChangeEvent = base.Event.bind(
    undefined, 'requestSelectionChange', true, false);

  var TimelineAnalysisView = ui.define('div');

  TimelineAnalysisView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'analysis';
    },

    set selection(selection) {
      this.textContent = '';

      var hitsByType = selection.getHitsOrganizedByType();
      if (selection.length == 1 &&
          hitsByType.sliceHits == 0 && hitsByType.counterSampleHits == 0) {
        if (hitsByType.objectSnapshotHits == 1) {
          // TODO(nduca): Put something here.
        }

        if (hitsByType.objectInstanceHits == 1) {
          // TODO(nduca): Put something here.
        }
      }

      var results = new tracing.analysis.AnalysisResults();
      tracing.analysis.analyzeHitsByType(results, hitsByType);
      this.appendChild(results);
    }
  };

  return {
    TimelineAnalysisView: TimelineAnalysisView,
    RequestSelectionChangeEvent: RequestSelectionChangeEvent,
  };
});
