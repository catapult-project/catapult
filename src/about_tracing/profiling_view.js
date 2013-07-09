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
base.require('ui.info_bar');
base.require('ui.overlay');

/*
 * Here is where we bring in modules that are used in about:tracing UI only.
 */
base.require('tracing.importer');
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

      this.selectingCategories = false;

      this.addEventListener('tracingControllerChange',
          this.refresh_.bind(this), true);
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

    refresh_: function() {
      if (!this.tracingController)
        return;

      this.saveBn_.disabled = true;

      if (!this.tracingController.traceEventData) {
        this.infoBar_.visible = false;
        return;
      }
      this.saveBn_.disabled = false;

      var traces = [this.tracingController.traceEventData];

      if (this.tracingController.systemTraceEvents)
        traces.push(this.tracingController.systemTraceEvents);

      var m = new tracing.TraceModel();
      try {
        m.importTraces(traces, true);
      } catch (e) {
        this.timelineView_.model = undefined;
        this.infoBar_.message =
            'There was an error while importing the traceData: ' +
            base.normalizeException(e).message;
        this.infoBar_.visible = true;
        return;
      }
      this.infoBar_.visible = false;
      this.timelineView_.model = m;
    },

    onKeypress_: function(event) {
      if (event.keyCode === 114 &&  // r
          !this.tracingController.isTracingEnabled &&
          !this.selectingCategories &&
          document.activeElement.nodeName !== 'INPUT') {
        this.onSelectCategories_();
      }
    },

    get selectingCategories() {
      return this.selectingCategories_;
    },

    set selectingCategories(val) {
      this.selectingCategories_ = val;
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

    ///////////////////////////////////////////////////////////////////////////

    onSelectCategories_: function() {
      this.selectingCategories = true;
      var tc = this.tracingController;
      tc.collectCategories();
      tc.addEventListener('categoriesCollected', this.onCategoriesCollected_);
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
      dlg.addEventListener('visibleChange', function(ev) {
        if (!dlg.visible)
          this.selectingCategories = false;
      }.bind(this));
      this.recordSelectionDialog_ = dlg;

      setTimeout(function() {
        tc.removeEventListener('categoriesCollected',
                               this.onCategoriesCollected_);
      }, 0);
    },

    onRecord_: function() {
      this.selectingCategories = false;

      var tc = this.tracingController;

      var categories = this.recordSelectionDialog_.categoryFilter();
      console.log('Recording: ' + categories);

      this.timelineView_.viewTitle = '-_-';
      tc.beginTracing(this.recordSelectionDialog_.isSystemTracingEnabled(),
                      this.recordSelectionDialog_.isContinuousTracingEnabled(),
                      this.recordSelectionDialog_.isSamplingEnabled(),
                      categories);

      tc.addEventListener('traceEnded', this.onTraceEnded_);
    },

    onTraceEnded_: function() {
      var tc = this.tracingController;
      this.timelineView_.viewTitle = '^_^';
      this.refresh_();
      setTimeout(function() {
        tc.removeEventListener('traceEnded', this.onTraceEnded_);
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

  return {
    ProfilingView: ProfilingView
  };
});
