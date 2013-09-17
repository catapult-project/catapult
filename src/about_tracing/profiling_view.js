// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview ProfilingView glues the View control to
 * TracingController.
 */
base.requireStylesheet('about_tracing.profiling_view');
base.requireStylesheet('ui.trace_viewer');
base.require('about_tracing.tracing_controller');
base.require('tracing.timeline_view');
base.require('tracing.record_selection_dialog');
base.require('ui');
base.require('ui.info_bar');
base.require('ui.overlay');

/*
 * Here is where we bring in modules that are used in about:tracing UI only.
 */
base.require('tracing.importer');
base.require('cc');
base.require('tcmalloc');
base.require('system_stats');
base.require('gpu');

base.exportTo('about_tracing', function() {
  /**
   * ProfilingView
   * @constructor
   * @extends {HTMLDivElement}
   */
  var ProfilingView = ui.define('div');

  ProfilingView.prototype = {
    __proto__: HTMLDivElement.prototype,

    decorate: function() {
      this.classList.add('profiling-view');

      this.canImportAsynchronously_ = true;

      // make the <list>/add/save/record element
      this.recordBn_ = document.createElement('button');
      this.recordBn_.className = 'record';
      this.recordBn_.textContent = 'Record';
      this.recordBn_.addEventListener('click',
          this.onProfilingViewRecordButtonClicked_.bind(this));

      this.saveBn_ = document.createElement('button');
      this.saveBn_.className = 'save';
      this.saveBn_.textContent = 'Save';
      this.saveBn_.addEventListener('click', this.onSave_.bind(this));

      this.loadBn_ = document.createElement('button');
      this.loadBn_.textContent = 'Load';
      this.loadBn_.addEventListener('click', this.onLoad_.bind(this));

      this.infoBar_ = new ui.InfoBar();
      this.infoBar_.visible = false;
      this.appendChild(this.infoBar_);

      this.timelineView_ = new tracing.TimelineView();
      this.timelineView_.leftControls.appendChild(this.recordBn_);
      this.timelineView_.leftControls.appendChild(this.saveBn_);
      this.timelineView_.leftControls.appendChild(this.loadBn_);
      this.appendChild(this.timelineView_);

      this.onKeypress_ = this.onKeypress_.bind(this);
      document.addEventListener('keypress', this.onKeypress_);

      this.onCategoriesCollected_ = this.onCategoriesCollected_.bind(this);
      this.onTraceEnded_ = this.onTraceEnded_.bind(this);

      this.dropHandler_ = this.dropHandler_.bind(this);
      this.ignoreHandler_ = this.ignoreHandler_.bind(this);
      document.addEventListener('dragstart', this.ignoreHandler_, false);
      document.addEventListener('dragend', this.ignoreHandler_, false);
      document.addEventListener('dragenter', this.ignoreHandler_, false);
      document.addEventListener('dragleave', this.ignoreHandler_, false);
      document.addEventListener('dragover', this.ignoreHandler_, false);
      document.addEventListener('drop', this.dropHandler_, false);

      this.currentRecordSelectionDialog_ = undefined;

      this.addEventListener('tracingControllerChange',
          this.beginRefresh_.bind(this), true);
    },

    // Detach all document event listeners. Without this the tests can get
    // confused as the element may still be listening when the next test runs.
    detach_: function() {
      document.removeEventListener('keypress', this.onKeypress_);
      document.removeEventListener('dragstart', this.ignoreHandler_);
      document.removeEventListener('dragend', this.ignoreHandler_);
      document.removeEventListener('dragenter', this.ignoreHandler_);
      document.removeEventListener('dragleave', this.ignoreHandler_);
      document.removeEventListener('dragover', this.ignoreHandler_);
      document.removeEventListener('drop', this.dropHandler_);
    },

    beginRefresh_: function() {
      if (!this.tracingController)
        return;
      if (this.refreshPending_)
        throw new Error('Cant refresh while a refresh is pending.');
      this.refreshPending_ = true;

      this.saveBn_.disabled = true;

      if (!this.tracingController.traceEventData) {
        this.infoBar_.visible = false;
        this.refreshPending_ = false;
        return;
      }
      this.saveBn_.disabled = false;

      var traces = [this.tracingController.traceEventData];

      if (this.tracingController.systemTraceEvents)
        traces.push(this.tracingController.systemTraceEvents);

      var m = new tracing.TraceModel();
      if (this.canImportAsynchronously_) {
        // Async import path.
        var p = m.importTracesWithProgressDialog(traces, true);
        p.then(
            function() {
              this.importDone_(m);
            }.bind(this),
            this.importFailed_.bind(this));
        return;
      }
      // Sync import path.
      try {
        m.importTraces(traces, true);
      } catch (e) {
        this.importFailed_(e);
        return;
      }
      this.importDone_(m);
    },

    importDone_: function(m) {
      this.infoBar_.visible = false;
      this.timelineView_.model = m;
      this.refreshPending_ = false;
    },

    importFailed_: function(e) {
      this.timelineView_.model = undefined;
      this.infoBar_.message =
          'There was an error while importing the traceData: ' +
          base.normalizeException(e).message;
      this.infoBar_.visible = true;
      this.refreshPending_ = false;
    },

    onKeypress_: function(event) {
      if (event.keyCode === 114 &&  // r
          !this.tracingController.isTracingEnabled &&
          !this.currentRecordSelectionDialog &&
          document.activeElement.nodeName !== 'INPUT') {
        this.onProfilingViewRecordButtonClicked_();
      }
    },

    get timelineView() {
      return this.timelineView_;
    },

    get tracingController() {
      return this.tracingController_;
    },

    set tracingController(newValue) {
      if (this.tracingController_)
        throw new Error('Can only set tracing controller once.');
      base.setPropertyAndDispatchChange(this, 'tracingController', newValue);
    },

    get canImportAsynchronously() {
      return this.canImportAsynchronously_;
    },

    set canImportAsynchronously(canImportAsynchronously) {
      this.canImportAsynchronously_ = canImportAsynchronously;
    },

    ///////////////////////////////////////////////////////////////////////////

    clickRecordButton: function() {
      this.recordBn_.click();
    },

    get currentRecordSelectionDialog() {
      return this.currentRecordSelectionDialog_;
    },

    onProfilingViewRecordButtonClicked_: function() {
      if (this.categoryCollectionPending_)
        return;
      this.categoryCollectionPending_ = true;
      var tc = this.tracingController;
      tc.collectCategories();
      tc.addEventListener('categoriesCollected', this.onCategoriesCollected_);
    },

    onCategoriesCollected_: function(event) {
      this.categoryCollectionPending_ = false;
      var tc = this.tracingController;

      var knownCategories = event.categories;
      // Do not allow categories with ,'s in their name.
      for (var i = 0; i < knownCategories.length; ++i) {
        var split = knownCategories[i].split(',');
        knownCategories[i] = split.shift();
        if (split.length > 0)
          knownCategories = knownCategories.concat(split);
      }

      var dlg = new tracing.RecordSelectionDialog();
      dlg.categories = knownCategories;
      dlg.settings_key = 'record_categories';
      dlg.supportsSystemTracing = this.tracingController.supportsSystemTracing;
      dlg.visible = true;
      dlg.addEventListener('recordclicked', function() {
        this.currentRecordSelectionDialog_ = undefined;

        var categories = dlg.categoryFilter();
        console.log('Recording: ' + categories);

        this.timelineView_.viewTitle = '-_-';
        tc.beginTracing(dlg.useSystemTracing,
                        dlg.useContinuousTracing,
                        dlg.useSampling,
                        categories);

        tc.addEventListener('traceEnded', this.onTraceEnded_);
      }.bind(this));
      dlg.addEventListener('visibleChange', function(ev) {
        if (dlg.visible)
          return;
        this.currentRecordSelectionDialog_ = undefined;
      }.bind(this));
      this.currentRecordSelectionDialog_ = dlg;

      setTimeout(function() {
        tc.removeEventListener('categoriesCollected',
                               this.onCategoriesCollected_);
      }, 0);
    },

    onTraceEnded_: function() {
      var tc = this.tracingController;
      this.timelineView_.viewTitle = '^_^';
      this.beginRefresh_();
      setTimeout(function() {
        tc.removeEventListener('traceEnded', this.onTraceEnded_);
      }, 0);
    },

    ///////////////////////////////////////////////////////////////////////////

    onSave_: function() {
      this.overlayEl_ = new ui.Overlay();
      this.overlayEl_.classList.add('profiling-overlay');

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Saving...';
      this.overlayEl_.userCanClose = false;
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
      this.overlayEl_.classList.add('profiling-overlay');

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Loading...';
      this.overlayEl_.appendChild(labelEl);
      this.overlayEl_.userCanClose = false;
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
          that.beginRefresh_();
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
            that.beginRefresh_();
          } catch (e) {
            console.log('Unable to import the provided trace file.', e.message);
          }
        };
        var is_binary = /[.]gz$/.test(filename) || /[.]zip$/.test(filename);
        if (is_binary)
          reader.readAsArrayBuffer(files[i]);
        else
          reader.readAsText(files[i]);
      }
      return false;
    }
  };

  return {
    ProfilingView: ProfilingView
  };
});
