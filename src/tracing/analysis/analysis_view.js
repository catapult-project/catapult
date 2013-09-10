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

      this.updateClassList_();
    },
    updateClassList_: function() {
      if (this.currentView_ instanceof tracing.analysis.AnalysisResults)
        this.classList.remove('viewing-old-style-analysis');
      else
        this.classList.add('viewing-old-style-analysis');

      if (this.currentView_ &&
          this.currentView_.requiresTallView) {
        this.classList.add('tall-mode');
      } else {
        this.classList.remove('tall-mode');
      }
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
      var eventsByType = selection.getEventsOrganizedByType();
      if (selection.length == 1 &&
          eventsByType.counterSamples.length == 0) {
        if (this.tryToProcessSelectionUsingCustomView(selection[0]))
          return;
      }

      this.changeViewType(tracing.analysis.AnalysisResults);

      this.currentView.clear();
      this.currentSelection_ = selection;
      tracing.analysis.analyzeEventsByType(this.currentView, eventsByType);
    },

    tryToProcessSelectionUsingCustomView: function(event) {
      var obj;
      var typeName;
      var viewBaseType;
      var defaultViewType;
      var viewProperty;
      if (event instanceof tracing.trace_model.ObjectSnapshot) {
        typeName = event.objectInstance.typeName;
        viewBaseType = tracing.analysis.ObjectSnapshotView;
        defaultViewType = tracing.analysis.DefaultObjectSnapshotView;
      } else if (event instanceof tracing.trace_model.ObjectInstance) {
        typeName = event.typeName;
        viewBaseType = tracing.analysis.ObjectInstanceView;
        defaultViewType = tracing.analysis.DefaultObjectInstanceView;
      } else if (event instanceof tracing.trace_model.Slice) {
        typeName = event.analysisTypeName;
        viewBaseType = tracing.analysis.SliceView;
        defaultViewType = undefined;
      } else {
        return false;
      }

      var customViewInfo = viewBaseType.getViewInfo(typeName);

      var viewType = customViewInfo ?
          customViewInfo.constructor : defaultViewType;

      // Some view types don't have default views. In those cases, we fall
      // back to the standard analysis sytem.
      if (!viewType)
        return false;

      this.changeViewType(viewType);
      this.currentView.modelEvent = event;
      return true;
    }
  };

  return {
    AnalysisView: AnalysisView
  };
});
