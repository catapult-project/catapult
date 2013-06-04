// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview Displays an analysis of the selection.
 */
base.requireStylesheet('tracing.analysis.analysis_view');

base.require('base.guid');
base.require('tracing.analysis.analysis_results');
base.require('tracing.analysis.analyze_selection');
base.require('tracing.analysis.default_object_view');
base.require('tracing.analysis.object_instance_view');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.slice_view');
base.require('tracing.analysis.util');
base.require('ui');
base.exportTo('tracing.analysis', function() {

  var AnalysisView = ui.define('div');

  AnalysisView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.className = 'analysis-view';

      this.currentView_ = undefined;
      this.currentSelection_ = undefined;
      this.selections_ = [];
      this.guid_ = base.GUID.allocate();

      window.addEventListener('popstate', this.onPopState.bind(this));
    },

    changeViewType: function(viewType) {
      if (this.currentView_ instanceof viewType)
        return;
      this.textContent = '';
      try {
        this.currentView_ = new viewType();
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
          hitsByType.counterSamples.length == 0) {
        if (this.tryToProcessSelectionUsingCustomViewer(selection[0]))
          return;
      }

      this.changeViewType(tracing.analysis.AnalysisResults);
      this.currentView.clear();
      this.currentSelection_ = selection;
      tracing.analysis.analyzeHitsByType(this.currentView, hitsByType);
    },

    tryToProcessSelectionUsingCustomViewer: function(hit) {
      var obj;
      var typeName;
      var viewBaseType;
      var defaultViewType;
      var viewProperty;
      var obj = hit.modelObject;
      if (hit instanceof tracing.SelectionObjectSnapshotHit) {
        typeName = obj.objectInstance.typeName;
        viewBaseType = tracing.analysis.ObjectSnapshotView;
        defaultViewType = tracing.analysis.DefaultObjectSnapshotView;
      } else if (hit instanceof tracing.SelectionObjectInstanceHit) {
        typeName = obj.typeName;
        viewBaseType = tracing.analysis.ObjectInstanceView;
        defaultViewType = tracing.analysis.DefaultObjectInstanceView;
      } else if (hit instanceof tracing.SelectionSliceHit) {
        typeName = obj.title;
        viewBaseType = tracing.analysis.SliceView;
        defaultViewType = undefined;
      } else {
        return false;
      }

      var customViewInfo = viewBaseType.getViewInfo(typeName);

      var viewType = customViewInfo ?
          customViewInfo.constructor : defaultViewType;

      // Some view types don't have default viewers. In those cases, we fall
      // back to the standard analysis sytem.
      if (!viewType)
        return false;

      this.changeViewType(viewType);
      this.currentView.modelObject = obj;
      return true;
    }
  };

  return {
    AnalysisView: AnalysisView
  };
});
