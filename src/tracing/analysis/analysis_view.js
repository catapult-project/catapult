// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Displays an analysis of the selection.
 */
base.requireStylesheet('tracing.analysis.analysis_view');

base.require('tracing.analysis.analyze_selection');
base.require('tracing.analysis.analysis_results');
base.require('tracing.analysis.object_instance_view');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.default_object_view');
base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  var AnalysisView = ui.define('div');

  AnalysisView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'analysis-view';
      this.snapshotViewRegistry = tracing.analysis.ObjectSnapshotView;
      this.instanceViewRegistry = tracing.analysis.ObjectInstanceView;

      this.currentView_ = undefined;
    },

    changeViewType: function(viewConstructor) {
      if (this.currentView_ instanceof viewConstructor)
        return;
      this.textContent = '';
      this.currentView_ = new viewConstructor();
      this.appendChild(this.currentView_);
    },

    get currentView() {
      return this.currentView_;
    },

    set selection(selection) {
      var hitsByType = selection.getHitsOrganizedByType();
      if (selection.length == 1 &&
          hitsByType.slices.length == 0 &&
          hitsByType.counterSamples.length == 0) {
        if (hitsByType.objectSnapshots.length == 1) {
          var snapshot = hitsByType.objectSnapshots[0].objectSnapshot;
          var viewConstructor = this.snapshotViewRegistry.getViewConstructor(
            snapshot.objectInstance.typeName);

          if (!viewConstructor)
            viewConstructor = tracing.analysis.DefaultObjectSnapshotView;

          this.changeViewType(viewConstructor);
          this.currentView.objectSnapshot = snapshot;
          return;
        }

        if (hitsByType.objectInstances.length == 1) {
          var instance = hitsByType.objectInstances[0].objectInstance;
          var viewConstructor = this.instanceViewRegistry.getViewConstructor(
            instance.typeName);

          if (!viewConstructor)
            viewConstructor = tracing.analysis.DefaultObjectInstanceView;

          this.changeViewType(viewConstructor);
          this.currentView.objectInstance = instance;
          return;
        }
      }

      this.changeViewType(tracing.analysis.AnalysisResults);
      this.currentView.clear();
      tracing.analysis.analyzeHitsByType(this.currentView, hitsByType);
    }
  };

  return {
    AnalysisView: AnalysisView
  };
});
