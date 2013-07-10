// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview State and UI for trace data collection.
 */
base.requireStylesheet('about_tracing.tracing_controller');

base.require('base.properties');
base.require('base.events');
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

    this.traceEventData_ = undefined;
    this.systemTraceEvents_ = undefined;

    this.onKeydown_ = this.onKeydown_.bind(this);
    this.onKeypress_ = this.onKeypress_.bind(this);

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
                           opt_enableSampling, opt_trace_categories) {
      if (this.tracingEnabled_)
        throw new Error('Tracing already begun.');

      this.stopButton_.hidden = false;
      this.statusDiv_.textContent = 'Tracing active.';
      this.overlay_.obeyCloseEvents = false;
      this.overlay_.visible = true;

      this.tracingEnabled_ = true;

      console.log('Beginning to trace...');
      this.statusDiv_.textContent = 'Tracing active.';

      var trace_options = [];
      trace_options.push(opt_trace_continuous ? 'record-continuously' :
                                                'record-until-full');
      if (opt_enableSampling)
        trace_options.push('enable-sampling');

      this.traceEventData_ = undefined;
      this.systemTraceEvents_ = undefined;
      this.sendFn_(
          'beginTracing',
          [
           opt_systemTracingEnabled || false,
           opt_trace_categories || '-test_*',
           trace_options.join(',')
          ]
      );
      this.beginRequestBufferPercentFull_();

      window.addEventListener('keypress', this.onKeypress_);
      window.addEventListener('keydown', this.onKeydown_);
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
    get traceEventData() {
      return this.traceEventData_;
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
      window.removeEventListener('keydown', this.onKeydown_);
      window.removeEventListener('keypress', this.onKeypress_);
      this.overlay_.visible = false;
      this.tracingEnabled_ = false;
      this.tracingEnding_ = false;

      if (traceDataString[traceDataString.length - 1] == ',')
        traceDataString = traceDataString.substr(0, traceDataString.length - 1);
      if (traceDataString[0] != '[')
        traceDataString = '[' + traceDataString;
      if (traceDataString[traceDataString.length - 1] != ']')
        traceDataString = traceDataString + ']';

      this.traceEventData_ = traceDataString;

      console.log('onEndTracingComplete p1 with ' +
                  this.traceEventData_.length + ' bytes of data.');
      var e = new base.Event('traceEnded');
      this.dispatchEvent(e);
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
    onLoadTraceFileComplete: function(traceDataString, opt_filename) {
      this.traceEventData_ = traceDataString;
      this.systemTraceEvents_ = undefined;

      var e = new base.Event('loadTraceFileComplete');
      e.filename = opt_filename || '';
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
      // this.traceEventData_ is already in JSON form, but now need to insert it
      // into a data structure containing metadata about the recording. To do
      // this "right," we should parse the traceEventData_, make the new data
      // structure and then JSONize the lot. But, the traceEventData_ is huge so
      // parsing it and stringifying it again is going to consume time and
      // memory.
      //
      // Instead, we make the new data strcture with a placeholder string,
      // JSONify it, then replace the placeholder string with the
      // traceEventData_.
      var data = {
        traceEvents: '__TRACE_EVENT_PLACEHOLDER__',
        systemTraceEvents: this.systemTraceEvents_,
        clientInfo: this.clientInfo_,
        gpuInfo: this.gpuInfo_
      };
      var dataAsString = JSON.stringify(data);
      dataAsString = dataAsString.replace('"__TRACE_EVENT_PLACEHOLDER__"',
                                          this.traceEventData_);
      this.sendFn_('saveTraceFile', [dataAsString]);
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
