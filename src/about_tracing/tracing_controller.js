// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview State and UI for trace data collection.
 */
base.requireStylesheet('about_tracing.tracing_controller');

base.require('base.event_target');
base.require('ui.overlay');

base.exportTo('about_tracing', function() {

  /**
   * The tracing controller is responsible for talking to tracing_ui.cc in
   * chrome
   * @constructor
   * @param {function(String, opt_Array.<String>} Function to be used to send
   * data to chrome.
   */
  function TracingController(sendFn) {
    this.sendFn_ = sendFn;
    this.overlay_ = new ui.Overlay();
    this.overlay_.className = 'tracing-overlay';

    this.statusDiv_ = document.createElement('div');
    this.overlay_.appendChild(this.statusDiv_);

    this.bufferPercentDiv_ = document.createElement('div');
    this.overlay_.appendChild(this.bufferPercentDiv_);

    this.stopButton_ = document.createElement('button');
    this.stopButton_.onclick = this.endTracing.bind(this);
    this.stopButton_.textContent = 'Stop tracing';
    this.overlay_.appendChild(this.stopButton_);

    this.traceEvents_ = [];
    this.systemTraceEvents_ = [];

    this.onKeydownBoundToThis_ = this.onKeydown_.bind(this);
    this.onKeypressBoundToThis_ = this.onKeypress_.bind(this);

    this.supportsSystemTracing_ = base.isChromeOS;

    if (this.sendFn_)
      this.sendFn_('tracingControllerInitialized');
  }

  TracingController.prototype = {
    __proto__: base.EventTarget.prototype,

    gpuInfo_: undefined,
    clientInfo_: undefined,
    tracingEnabled_: false,
    tracingEnding_: false,
    systemTraceDataFilename_: undefined,

    get supportsSystemTracing() {
      return this.supportsSystemTracing_;
    },

    onRequestBufferPercentFullComplete: function(percent_full) {
      if (!this.overlay_.visible)
        return;

      window.setTimeout(this.beginRequestBufferPercentFull_.bind(this), 500);

      var newText = 'Buffer usage: ' +
          Math.round(100 * percent_full) + '%';
      if (this.bufferPercentDiv_.textContent != newText)
        this.bufferPercentDiv_.textContent = newText;
    },

    /**
     * Begin requesting the buffer fullness
     */
    beginRequestBufferPercentFull_: function() {
      this.sendFn_('beginRequestBufferPercentFull');
    },

    /**
     * Called by info_view to empty the trace buffer
     *
     * |opt_trace_categories| is a comma-delimited list of category wildcards.
     * A category can have an optional '-' prefix to make it an excluded
     * category.  All the same rules apply above, so for example, having both
     * included and excluded categories in the same list would not be
     * supported.
     *
     * Example: beginTracing("test_MyTest*");
     * Example: beginTracing("test_MyTest*,test_OtherStuff");
     * Example: beginTracing("-excluded_category1,-excluded_category2");
     */
    beginTracing: function(opt_systemTracingEnabled, opt_trace_continuous,
                           opt_trace_categories) {
      if (this.tracingEnabled_)
        throw new Error('Tracing already begun.');

      this.stopButton_.hidden = false;
      this.statusDiv_.textContent = 'Tracing active.';
      this.overlay_.visible = true;
      this.overlay_.defaultClickShouldClose = false;

      this.tracingEnabled_ = true;

      console.log('Beginning to trace...');
      this.statusDiv_.textContent = 'Tracing active.';

      var trace_options = (opt_trace_continuous ? 'record-continuously' :
                                                  'record-until-full');

      this.failedTraceDataString_ = undefined;
      this.traceEvents_ = [];
      this.systemTraceEvents_ = [];
      this.sendFn_(
          'beginTracing',
          [
           opt_systemTracingEnabled || false,
           opt_trace_categories || '-test_*',
           trace_options
          ]
      );
      this.beginRequestBufferPercentFull_();

      var e = new base.Event('traceBegun');
      e.events = this.traceEvents_;
      this.dispatchEvent(e);

      e = new base.Event('traceEventsChanged');
      e.numEvents = this.traceEvents_.length;
      this.dispatchEvent(e);

      window.addEventListener('keypress', this.onKeypressBoundToThis_);
      window.addEventListener('keydown', this.onKeydownBoundToThis_);
    },

    onKeydown_: function(e) {
      if (e.keyCode == 27) {
        this.endTracing();
      }
    },

    onKeypress_: function(e) {
      if (e.keyIdentifier == 'Enter') {
        this.endTracing();
      }
    },

    /**
     * Called from gpu c++ code when ClientInfo is updated.
     */
    onClientInfoUpdate: function(clientInfo) {
      this.clientInfo_ = clientInfo;
    },

    /**
     * Called from gpu c++ code when GPU Info is updated.
     */
    onGpuInfoUpdate: function(gpuInfo) {
      this.gpuInfo_ = gpuInfo;
    },

    /**
     * Checks whether tracing is enabled
     */
    get isTracingEnabled() {
      return this.tracingEnabled_;
    },

    /**
     * Gets the currently traced events. If tracing is active, then
     * this can change on the fly.
     */
    get traceEvents() {
      return this.traceEvents_;
    },

    get failedTraceDataString() {
      return this.failedTraceDataString_;
    },

    /**
     * Called to finish tracing and update all views.
     */
    endTracing: function() {
      if (!this.tracingEnabled_) throw new Error('Tracing not begun.');
      if (this.tracingEnding_) return;
      this.tracingEnding_ = true;

      this.statusDiv_.textContent = 'Ending trace...';
      console.log('Finishing trace');
      this.statusDiv_.textContent = 'Downloading trace data...';
      this.stopButton_.hidden = true;
      // delay sending endTracingAsync until we get a chance to
      // update the screen...
      var that = this;
      window.setTimeout(function() {
        that.sendFn_('endTracingAsync');
      }, 100);
    },

    /**
     * Called by the browser when all processes complete tracing.
     */
    onEndTracingComplete: function(traceDataString) {
      window.removeEventListener('keydown', this.onKeydownBoundToThis_);
      window.removeEventListener('keypress', this.onKeypressBoundToThis_);
      this.overlay_.visible = false;
      this.tracingEnabled_ = false;
      this.tracingEnding_ = false;

      if (traceDataString[traceDataString.length - 1] == ',')
        traceDataString = traceDataString.substr(0, traceDataString.length - 1);
      if (traceDataString[0] != '[')
        traceDataString = '[' + traceDataString;
      if (traceDataString[traceDataString.length - 1] != ']')
        traceDataString = traceDataString + ']';

      var ok = false;
      var errorMessage = undefined;
      try {
        this.traceEvents_ = JSON.parse(traceDataString);
        ok = true;
      } catch (e) {
        errorMessage = e;
      }

      if (ok) {
        console.log('onEndTracingComplete p1 with ' +
                    this.traceEvents_.length + ' events.');
        var e = new base.Event('traceEnded');
        e.events = this.traceEvents_;
        this.dispatchEvent(e);
        return;
      }

      // Load error
      console.log('Error while importing traceData: ' + errorMessage);
      this.failedTraceDataString_ = traceDataString;
      this.traceEvents_ = [];
      var overlay = new ui.Overlay();

      var statusDiv = document.createElement('div');
      statusDiv.textContent =
        'There was an error while importing the traceData: ' + errorMessage +
        'Would you like to save it?';
      statusDiv.style.maxWidth = '350px';

      var saveButton = document.createElement('button');
      saveButton.textContent = 'Save it';

      var cancelButton = document.createElement('button');
      cancelButton.textContent = 'Cancel';

      var buttonContainer = document.createElement('div');
      buttonContainer.style.display = '-webkit-flex';
      buttonContainer.style.webkitFlexDirection = 'row-reverse';
      buttonContainer.appendChild(cancelButton);
      buttonContainer.appendChild(saveButton);
      overlay.appendChild(statusDiv);
      overlay.appendChild(buttonContainer);
      overlay.visible = true;
      overlay.autoClose = true;
      function cancel() {
        if (overlay.visible)
          overlay.visible = false;
        var e = new base.Event('traceEnded');
        e.events = this.traceEvents_;
        this.dispatchEvent(e);
      }
      cancel = cancel.bind(this);

      cancelButton.addEventListener('click', cancel);
      overlay.addEventListener('visibleChange', cancel);
      function onSaveDone() {
        setTimeout(function() {
          this.removeEventListener('saveTraceFileComplete', onSaveDone);
        }.bind(this));

        var e = new base.Event('traceEnded');
        e.events = this.traceEvents_;
        this.dispatchEvent(e);
      }
      onSaveDone = onSaveDone.bind(this);
      this.addEventListener('saveTraceFileComplete', onSaveDone);
      saveButton.addEventListener('click', function() {
        overlay.visible = false;
        this.beginSaveTraceFile();
      }.bind(this));
    },

    collectCategories: function() {
      this.sendFn_('getKnownCategories');
    },

    onKnownCategoriesCollected: function(categories) {
      var e = new base.Event('categoriesCollected');
      e.categories = categories;
      this.dispatchEvent(e);
    },


    /**
     * Called by tracing c++ code when new system trace data arrives.
     */
    onSystemTraceDataCollected: function(events) {
      console.log('onSystemTraceDataCollected with ' +
                  events.length + ' chars of data.');
      this.systemTraceEvents_ = events;
    },

    /**
     * Gets the currentl system trace events. If tracing is active, then
     * this can change on the fly.
     */
    get systemTraceEvents() {
      return this.systemTraceEvents_;
    },

    /**
     * Tells browser to put up a load dialog and load the trace file
     */
    beginLoadTraceFile: function() {
      this.sendFn_('loadTraceFile');
    },

    /**
     * Called by the browser when a trace file is loaded.
     */
    onLoadTraceFileComplete: function(traceDataString) {
      var data;
      this.failedTraceDataString_ = undefined;
      try {
        data = JSON.parse(traceDataString);
      } catch (e) {
        console.log('Trace file did not parse.', e);
        data = [];
      }
      if (data.traceEvents) {
        this.traceEvents_ = data.traceEvents;
      } else { // path for loading traces saved without metadata
        if (!data.length)
          console.log('Expected an array when loading the trace file');
        else
          this.traceEvents_ = data;
      }

      if (data.systemTraceEvents)
        this.systemTraceEvents_ = data.systemTraceEvents;
      else
        this.systemTraceEvents_ = [];

      var e = new base.Event('loadTraceFileComplete');
      e.events = this.traceEvents_;
      this.dispatchEvent(e);
    },

    /**
     * Called by the browser when loading a trace file was canceled.
     */
    onLoadTraceFileCanceled: function() {
      base.dispatchSimpleEvent(this, 'loadTraceFileCanceled');
    },

    /**
     * Tells browser to put up a save dialog and save the trace file
     */
    beginSaveTraceFile: function() {
      if (this.failedTraceDataString_) {
        this.sendFn_('saveTraceFile', [this.failedTraceDataString_]);
        return;
      }

      var data = {
        traceEvents: this.traceEvents_,
        systemTraceEvents: this.systemTraceEvents_,
        clientInfo: this.clientInfo_,
        gpuInfo: this.gpuInfo_
      };
      this.sendFn_('saveTraceFile', [JSON.stringify(data)]);
    },

    /**
     * Called by the browser when a trace file is saveed.
     */
    onSaveTraceFileComplete: function() {
      base.dispatchSimpleEvent(this, 'saveTraceFileComplete');
    },

    /**
     * Called by the browser when saving a trace file was canceled.
     */
    onSaveTraceFileCanceled: function() {
      base.dispatchSimpleEvent(this, 'saveTraceFileCanceled');
    }
  };
  return {
    TracingController: TracingController
  };
});
