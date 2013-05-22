// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview ProfilingView glues the View control to
 * TracingController.
 */
base.requireStylesheet('about_tracing.profiling_view');
base.require('about_tracing.tracing_controller');
base.require('tracing.timeline_view');
base.require('tracing.record_selection_dialog');
base.require('ui');
base.require('ui.overlay');

/*
 * Here is where we bring in modules that are used in about:tracing UI only.
 */
base.require('tracing.importer.linux_perf_importer');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.importer.v8_log_importer');
base.require('cc');
base.require('tcmalloc');

base.exportTo('about_tracing', function() {
  /**
   * ProfilingView
   * @constructor
   * @extends {HTMLDivElement}
   */
  var ProfilingView = ui.define('div');

  ProfilingView.prototype = {
    __proto__: HTMLDivElement.prototype,

    traceEvents_: [],
    systemTraceEvents_: [],

    decorate: function() {
      this.classList.add('profiling-view');

      // make the <list>/add/save/record element
      this.recordBn_ = document.createElement('button');
      this.recordBn_.className = 'record';
      this.recordBn_.textContent = 'Record';
      this.recordBn_.addEventListener('click',
                                      this.onSelectCategories_.bind(this));

      this.saveBn_ = document.createElement('button');
      this.saveBn_.className = 'save';
      this.saveBn_.textContent = 'Save';
      this.saveBn_.addEventListener('click', this.onSave_.bind(this));

      this.loadBn_ = document.createElement('button');
      this.loadBn_.textContent = 'Load';
      this.loadBn_.addEventListener('click', this.onLoad_.bind(this));

      this.timelineView_ = new tracing.TimelineView();
      this.timelineView_.leftControls.appendChild(this.recordBn_);
      this.timelineView_.leftControls.appendChild(this.saveBn_);
      this.timelineView_.leftControls.appendChild(this.loadBn_);
      this.appendChild(this.timelineView_);

      document.addEventListener('keypress', this.onKeypress_.bind(this));

      this.onCategoriesCollectedBoundToThis_ =
          this.onCategoriesCollected_.bind(this);
      this.onTraceEndedBoundToThis_ = this.onTraceEnded_.bind(this);

      document.addEventListener('dragstart', this.ignoreHandler_, false);
      document.addEventListener('dragend', this.ignoreHandler_, false);
      document.addEventListener('dragenter', this.ignoreHandler_, false);
      document.addEventListener('dragleave', this.ignoreHandler_, false);
      document.addEventListener('dragover', this.ignoreHandler_, false);
      document.addEventListener('drop', this.dropHandler_.bind(this), false);

      this.refresh_();
    },

    didSetTracingController_: function(value, oldValue) {
      if (oldValue)
        throw new Error('Can only set tracing controller once.');

      this.refresh_();
    },

    refresh_: function() {
      if (!this.tracingController)
        return;

      var traceEvents = this.tracingController.traceEvents;
      var hasEvents = traceEvents && traceEvents.length;
      this.saveBn_.disabled = !hasEvents;

      if (!hasEvents) return;

      var traces = [traceEvents];
      if (this.tracingController.systemTraceEvents.length)
        traces.push(this.tracingController.systemTraceEvents);

      var m = new tracing.Model();
      m.importTraces(traces, true);
      this.timelineView_.model = m;
    },

    onKeypress_: function(event) {
      if (event.keyCode === 114 &&  // r
          !this.tracingController.isTracingEnabled &&
          document.activeElement.nodeName !== 'INPUT') {
        this.onSelectCategories_();
      }
    },

    get timelineView() {
      return this.timelineView_;
    },

    ///////////////////////////////////////////////////////////////////////////

    onSelectCategories_: function() {
      var tc = this.tracingController;
      tc.collectCategories();
      tc.addEventListener('categoriesCollected',
                          this.onCategoriesCollectedBoundToThis_);
    },

    onCategoriesCollected_: function(event) {
      var tc = this.tracingController;

      var categories = event.categories;
      var categories_length = categories.length;
      // Do not allow categories with ,'s in their name.
      for (var i = 0; i < categories_length; ++i) {
        var split = categories[i].split(',');
        categories[i] = split.shift();
        if (split.length > 0)
          categories = categories.concat(split);
      }

      var dlg = new tracing.RecordSelectionDialog();
      dlg.categories = categories;
      dlg.settings = this.timelineView_.settings;
      dlg.settings_key = 'record_categories';
      dlg.recordCallback = this.onRecord_.bind(this);
      dlg.showSystemTracing = this.tracingController.supportsSystemTracing;
      dlg.visible = true;
      this.recordSelectionDialog_ = dlg;

      setTimeout(function() {
        tc.removeEventListener('categoriesCollected',
                               this.onCategoriesCollectedBoundToThis_);
      }, 0);
    },

    onRecord_: function() {
      var tc = this.tracingController;

      var categories = this.recordSelectionDialog_.categoryFilter();
      console.log('Recording: ' + categories);

      this.timelineView_.viewTitle = '-_-';
      tc.beginTracing(this.recordSelectionDialog_.isSystemTracingEnabled(),
                      this.recordSelectionDialog_.isContinuousTracingEnabled(),
                      categories);

      tc.addEventListener('traceEnded', this.onTraceEndedBoundToThis_);
    },

    onTraceEnded_: function() {
      var tc = this.tracingController;
      this.timelineView_.viewTitle = '^_^';
      this.refresh_();
      setTimeout(function() {
        tc.removeEventListener('traceEnded', this.onTraceEndedBoundToThis_);
      }, 0);
    },

    ///////////////////////////////////////////////////////////////////////////

    onSave_: function() {
      this.overlayEl_ = new ui.Overlay();
      this.overlayEl_.className = 'profiling-overlay';

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Saving...';
      this.overlayEl_.appendChild(labelEl);
      this.overlayEl_.visible = true;

      var that = this;
      var tc = this.tracingController;
      function response() {
        that.overlayEl_.visible = false;
        that.overlayEl_ = undefined;
        setTimeout(function() {
          tc.removeEventListener('saveTraceFileComplete', response);
          tc.removeEventListener('saveTraceFileCanceled', response);
        }, 0);
      }
      tc.addEventListener('saveTraceFileComplete', response);
      tc.addEventListener('saveTraceFileCanceled', response);
      tc.beginSaveTraceFile();
    },

    ///////////////////////////////////////////////////////////////////////////

    onLoad_: function() {
      this.overlayEl_ = new ui.Overlay();
      this.overlayEl_.className = 'profiling-overlay';

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Loading...';
      this.overlayEl_.appendChild(labelEl);
      this.overlayEl_.visible = true;

      var that = this;
      var tc = this.tracingController;
      this.tracingController.beginLoadTraceFile();
      function response(e) {
        that.overlayEl_.visible = false;
        that.overlayEl_ = undefined;
        if (e.type === 'loadTraceFileComplete') {
           var nameParts = e.filename.split(/\//);
           if (nameParts.length > 0)
             that.timelineView_.viewTitle = nameParts[nameParts.length - 1];
           else
             that.timelineView_.viewTitle = '^_^';
          that.refresh_();
        }

        setTimeout(function() {
          tc.removeEventListener('loadTraceFileComplete', response);
          tc.removeEventListener('loadTraceFileCanceled', response);
        }, 0);
      }

      tc.addEventListener('loadTraceFileComplete', response);
      tc.addEventListener('loadTraceFileCanceled', response);
    },

    ///////////////////////////////////////////////////////////////////////////

    ignoreHandler_: function(e) {
      e.preventDefault();
      return false;
    },

    dropHandler_: function(e) {
      e.stopPropagation();
      e.preventDefault();

      var that = this;
      var files = e.dataTransfer.files;
      var files_len = files.length;
      for (var i = 0; i < files_len; ++i) {
        var reader = new FileReader();
        var filename = files[i].name;
        reader.onload = function(data) {
          try {
            that.tracingController.onLoadTraceFileComplete(data.target.result,
                                                           filename);
            that.timelineView_.viewTitle = filename;
            that.refresh_();
          } catch (e) {
            console.log('Unable to import the provided trace file.', e.message);
          }
        };
        reader.readAsText(files[i]);
      }
      return false;
    }
  };

  base.defineProperty(ProfilingView, 'tracingController', base.PropertyKind.JS,
      ProfilingView.prototype.didSetTracingController_);

  return {
    ProfilingView: ProfilingView
  };
});
