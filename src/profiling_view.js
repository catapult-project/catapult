// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview ProfilingView glues the TimelineView control to
 * TracingController.
 */
cr.define('tracing', function() {
  /**
   * ProfilingView
   * @constructor
   * @extends {ui.TabPanel}
   */
  var ProfilingView = cr.ui.define(cr.ui.TabPanel);

  ProfilingView.prototype = {
    __proto__: cr.ui.TabPanel.prototype,

    traceEvents_: [],
    systemTraceEvents_: [],

    decorate: function() {
      cr.ui.TabPanel.prototype.decorate.apply(this);
      this.classList.add('profiling-view');

      // make the <list>/add/save/record element
      this.recordBn_ = document.createElement('button');
      this.recordBn_.className = 'record';
      this.recordBn_.textContent = 'Record';
      this.recordBn_.addEventListener('click', this.onRecord_.bind(this));

      this.saveBn_ = document.createElement('button');
      this.saveBn_.textContent = 'Save';
      this.saveBn_.addEventListener('click', this.onSave_.bind(this));

      this.loadBn_ = document.createElement('button');
      this.loadBn_.textContent = 'Load';
      this.loadBn_.addEventListener('click', this.onLoad_.bind(this));

      if (cr.isChromeOS) {
        this.systemTracingBn_ = document.createElement('input');
        this.systemTracingBn_.type = 'checkbox';
        this.systemTracingBn_.checked = true;

        var systemTracingLabelEl = document.createElement('div');
        systemTracingLabelEl.className = 'label';
        systemTracingLabelEl.textContent = 'System events';
        systemTracingLabelEl.appendChild(this.systemTracingBn_);
      }

      this.timelineView_ = new tracing.TimelineView();
      this.timelineView_.leftControls.appendChild(this.recordBn_);
      this.timelineView_.leftControls.appendChild(this.saveBn_);
      this.timelineView_.leftControls.appendChild(this.loadBn_);
      if (cr.isChromeOS)
        this.timelineView_.leftControls.appendChild(this.systemTracingBn_);

      this.appendChild(this.timelineView_);

      document.addEventListener('keypress', this.onKeypress_.bind(this));

      this.refresh_();
    },

    didSetTracingController_: function(value, oldValue) {
      if (oldValue)
        throw 'Can only set tracing controller once.';

      this.tracingController_.addEventListener('traceEnded',
          this.onRecordDone_.bind(this));
      this.tracingController_.addEventListener('loadTraceFileComplete',
          this.onLoadTraceFileComplete_.bind(this));
      this.tracingController_.addEventListener('saveTraceFileComplete',
          this.onSaveTraceFileComplete_.bind(this));
      this.tracingController_.addEventListener('loadTraceFileCanceled',
          this.onLoadTraceFileCanceled_.bind(this));
      this.tracingController_.addEventListener('saveTraceFileCanceled',
          this.onSaveTraceFileCanceled_.bind(this));
      this.refresh_();
    },

    refresh_: function() {
      if (!this.tracingController_)
        return;

      var traceEvents = this.tracingController_.traceEvents;
      var hasEvents = traceEvents && traceEvents.length;

      this.saveBn_.disabled = !hasEvents;

      if (!hasEvents) return;

      var m = new tracing.TimelineModel();
      m.importEvents(traceEvents, true,
                     [this.tracingController_.systemTraceEvents]);
      this.timelineView_.model = m;
    },

    onKeypress_: function(event) {
      if (event.keyCode == 114 && !this.tracingController_.isTracingEnabled) {
        this.onRecord_();
      }
    },

    get timelineView() {
      return this.timelineView_;
    },

    ///////////////////////////////////////////////////////////////////////////

    onRecord_: function() {
      var systemTracingEnabled;
      if (this.systemTracingBn_)
        systemTracingEnabled = this.systemTracingBn_.checked;
      else
        systemTracingEnabled = false;
      this.tracingController_.beginTracing(systemTracingEnabled);
    },

    onRecordDone_: function() {
      this.refresh_();
    },

    ///////////////////////////////////////////////////////////////////////////

    onSave_: function() {
      this.overlayEl_ = new tracing.Overlay();
      this.overlayEl_.className = 'profiling-overlay';

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Saving...';
      this.overlayEl_.appendChild(labelEl);
      this.overlayEl_.visible = true;

      this.tracingController_.beginSaveTraceFile();
    },

    onSaveTraceFileComplete_: function(e) {
      this.overlayEl_.visible = false;
      this.overlayEl_ = undefined;
    },

    onSaveTraceFileCanceled_: function(e) {
      this.overlayEl_.visible = false;
      this.overlayEl_ = undefined;
    },

    ///////////////////////////////////////////////////////////////////////////

    onLoad_: function() {
      this.overlayEl_ = new tracing.Overlay();
      this.overlayEl_.className = 'profiling-overlay';

      var labelEl = document.createElement('div');
      labelEl.className = 'label';
      labelEl.textContent = 'Loading...';
      this.overlayEl_.appendChild(labelEl);
      this.overlayEl_.visible = true;

      this.tracingController_.beginLoadTraceFile();
    },

    onLoadTraceFileComplete_: function(e) {
      this.overlayEl_.visible = false;
      this.overlayEl_ = undefined;

      this.refresh_();
    },

    onLoadTraceFileCanceled_: function(e) {
      this.overlayEl_.visible = false;
      this.overlayEl_ = undefined;
    }
  };

  cr.defineProperty(ProfilingView, 'tracingController', cr.PropertyKind.JS,
                    ProfilingView.prototype.didSetTracingController_);

  return {
    ProfilingView: ProfilingView
  };
});
