// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview State and UI for trace data collection.
 */
cr.define('tracing', function() {

  function TracingController() {
    this.overlay_ = document.createElement('div');
    this.overlay_.className = 'tracing-overlay';

    cr.ui.decorate(this.overlay_, tracing.Overlay);

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

    chrome.send('tracingControllerInitialized');
  }

  TracingController.prototype = {
    __proto__: cr.EventTarget.prototype,

    gpuInfo_: undefined,
    clientInfo_: undefined,
    tracingEnabled_: false,
    tracingEnding_: false,
    systemTraceDataFilename_: undefined,

    onRequestBufferPercentFullComplete: function(percent_full) {
      if (!this.overlay_.visible)
        return;

      window.setTimeout(this.beginRequestBufferPercentFull_.bind(this), 250);

      this.bufferPercentDiv_.textContent = 'Buffer usage: ' +
          Math.round(100 * percent_full) + '%';
    },

    /**
     * Begin requesting the buffer fullness
     */
    beginRequestBufferPercentFull_: function() {
      chrome.send('beginRequestBufferPercentFull');
    },

    /**
     * Called by info_view to empty the trace buffer
     */
    beginTracing: function(opt_systemTracingEnabled) {
      if (this.tracingEnabled_)
        throw Error('Tracing already begun.');

      this.stopButton_.hidden = false;
      this.statusDiv_.textContent = 'Tracing active.';
      this.overlay_.visible = true;

      this.tracingEnabled_ = true;

      console.log('Beginning to trace...');
      this.statusDiv_.textContent = 'Tracing active.';

      this.traceEvents_ = [];
      this.systemTraceEvents_ = [];
      chrome.send('beginTracing', [opt_systemTracingEnabled || false]);
      this.beginRequestBufferPercentFull_();

      var e = new cr.Event('traceBegun');
      e.events = this.traceEvents_;
      this.dispatchEvent(e);

      e = new cr.Event('traceEventsChanged');
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

    /**
     * Called by tracing c++ code when new trace data arrives.
     */
    onTraceDataCollected: function(events) {
      this.statusDiv_.textContent = 'Processing trace...';
      this.traceEvents_.push.apply(this.traceEvents_, events);
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
      window.setTimeout(function() {
        chrome.send('endTracingAsync');
      }, 100);
    },

    /**
     * Called by the browser when all processes complete tracing.
     */
    onEndTracingComplete: function() {
      window.removeEventListener('keydown', this.onKeydownBoundToThis_);
      window.removeEventListener('keypress', this.onKeypressBoundToThis_);
      this.overlay_.visible = false;
      this.tracingEnabled_ = false;
      this.tracingEnding_ = false;
      console.log('onEndTracingComplete p1 with ' +
                  this.traceEvents_.length + ' events.');
      var e = new cr.Event('traceEnded');
      e.events = this.traceEvents_;
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
      chrome.send('loadTraceFile');
    },

    /**
     * Called by the browser when a trace file is loaded.
     */
    onLoadTraceFileComplete: function(data) {
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

      var e = new cr.Event('loadTraceFileComplete');
      e.events = this.traceEvents_;
      this.dispatchEvent(e);
    },

    /**
     * Called by the browser when loading a trace file was canceled.
     */
    onLoadTraceFileCanceled: function() {
      cr.dispatchSimpleEvent(this, 'loadTraceFileCanceled');
    },

    /**
     * Tells browser to put up a save dialog and save the trace file
     */
    beginSaveTraceFile: function(traceEvents, systemTraceEvents) {
      var data = {
        traceEvents: this.traceEvents_,
        systemTraceEvents: this.systemTraceEvents_,
        clientInfo: this.clientInfo_,
        gpuInfo: this.gpuInfo_
      };
      chrome.send('saveTraceFile', [JSON.stringify(data)]);
    },

    /**
     * Called by the browser when a trace file is saveed.
     */
    onSaveTraceFileComplete: function() {
      cr.dispatchSimpleEvent(this, 'saveTraceFileComplete');
    },

    /**
     * Called by the browser when saving a trace file was canceled.
     */
    onSaveTraceFileCanceled: function() {
      cr.dispatchSimpleEvent(this, 'saveTraceFileCanceled');
    },

    selfTest: function() {
      this.beginTracing();
      window.setTimeout(this.endTracing.bind(This), 500);
    }
  };
  return {
    TracingController: TracingController
  };
});
