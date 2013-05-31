// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Displays an analysis of the selection.
 */
base.requireStylesheet('tracing.analysis.analysis_view');

base.require('base.guid');
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
      this.currentSelection_ = undefined;
      this.selections_ = [];
      this.guid_ = base.GUID.allocate();

      window.addEventListener('popstate', this.onPopState.bind(this));
    },

    changeViewType: function(viewConstructor) {
      if (this.currentView_ instanceof viewConstructor)
        return;
      this.textContent = '';
      try {
        this.currentView_ = new viewConstructor();
        this.appendChild(this.currentView_);
      } catch (e) {
        this.currentView_ = undefined;
        throw e;
      }
      if (this.currentView_ instanceof tracing.analysis. AnalysisResults)
        this.classList.remove('viewing-object');
      else
        this.classList.add('viewing-object');
    },

    get currentView() {
      return this.currentView_;
    },

    get selection() {
      return this.currentSelection_;
    },

    set selection(selection) {
      this.selections_.push(selection);

      var state = {
        view_guid: this.guid_,
        selection_guid: selection.guid
      };
      window.history.pushState(state);

      this.processSelection(selection);
    },

    clearSelectionHistory: function() {
      this.selections_ = [];
    },

    onPopState: function(event) {
      if ((event.state === null) ||
          (event.state.view_guid !== this.guid_))
        return;

      var idx;
      for (idx = 0; idx < this.selections_.length; ++idx) {
        if (this.selections_[idx].guid === event.state.selection_guid)
          break;
      }

      if (idx >= this.selections_.length)
        return;

      this.processSelection(this.selections_[idx]);
      event.stopPropagation();
    },

    processSelection: function(selection) {
      var hitsByType = selection.getHitsOrganizedByType();
      if (selection.length == 1 &&
          hitsByType.slices.length == 0 &&
          hitsByType.counterSamples.length == 0) {
        if (hitsByType.objectSnapshots.length == 1) {
          var snapshot = hitsByType.objectSnapshots[0].objectSnapshot;
          var viewInfo = this.snapshotViewRegistry.getViewInfo(
              snapshot.objectInstance.typeName);

          var viewConstructor;
          if (viewInfo)
            viewConstructor = viewInfo.constructor;
          else
            viewConstructor = tracing.analysis.DefaultObjectSnapshotView;

          this.changeViewType(viewConstructor);
          this.currentView.objectSnapshot = snapshot;
          return;
        }

        if (hitsByType.objectInstances.length == 1) {
          var instance = hitsByType.objectInstances[0].objectInstance;
          var viewInfo = this.instanceViewRegistry.getViewInfo(
              instance.typeName);

          var viewConstructor;
          if (viewInfo)
            viewConstructor = viewInfo.constructor;
          else
            viewConstructor = tracing.analysis.DefaultObjectInstanceView;

          this.changeViewType(viewConstructor);
          this.currentView.objectInstance = instance;
          return;
        }
      }

      this.changeViewType(tracing.analysis.AnalysisResults);
      this.currentView.clear();
      this.currentSelection_ = selection;
      tracing.analysis.analyzeHitsByType(this.currentView, hitsByType);
    }
  };

  return {
    AnalysisView: AnalysisView
  };
});
