// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.analysis.util');
tvcm.require('tracing.timeline_view_side_panel');
tvcm.require('tvcm.iteration_helpers');
tvcm.require('tvcm.statistics');
tvcm.require('tvcm.ui.dom_helpers');
tvcm.require('tvcm.ui.line_chart');

tvcm.requireTemplate('tracing.input_latency_side_panel');

tvcm.exportTo('tracing', function() {

  function createLatencyLineChart(data, title) {
    var chart = new tvcm.ui.LineChart();
    var width = 600;
    if (document.body.clientWidth != undefined)
      width = document.body.clientWidth * 0.5;
    chart.setSize({width: width, height: chart.height});
    chart.chartTitle = title;
    chart.data = data;
    return chart;
  }

  function getSlicesIntersectingRange(rangeOfInterest, slices) {
    var slicesInFilterRange = [];
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (rangeOfInterest.intersectsExplicitRange(slice.start, slice.end))
        slicesInFilterRange.push(slice);
    }
    return slicesInFilterRange;
  }

  var BROWSER_PROCESS_NAME = 'CrBrowserMain';

  function findBrowserProcess(model) {
    var browserProcess;
    model.getAllProcesses().forEach(function(process) {
      if (process.findAllThreadsNamed(BROWSER_PROCESS_NAME).length != 0)
        browserProcess = process;
    });
    return browserProcess;
  }

  var MAIN_RENDERING_STATS =
      'BenchmarkInstrumentation::MainThreadRenderingStats';
  var IMPL_RENDERING_STATS =
      'BenchmarkInstrumentation::ImplThreadRenderingStats';

  var MAIN_FRAMETIME_TYPE = 'main_frametime_type';
  var IMPL_FRAMETIME_TYPE = 'impl_frametime_type';

  function getFrametimeData(model, frametimeType, rangeOfInterest) {
    var mainRenderingSlices = [];
    var implRenderingSlices = [];
    var browserProcess = findBrowserProcess(model);
    if (browserProcess != undefined) {
      browserProcess.iterateAllEvents(function(event) {
        if (event.title === MAIN_RENDERING_STATS)
          mainRenderingSlices.push(event);
        if (event.title === IMPL_RENDERING_STATS)
          implRenderingSlices.push(event);
      });
    }

    var renderingSlices = [];
    if (frametimeType === MAIN_FRAMETIME_TYPE) {
      renderingSlices = getSlicesIntersectingRange(rangeOfInterest,
                                                   mainRenderingSlices);
    } else if (frametimeType === IMPL_FRAMETIME_TYPE) {
      renderingSlices = getSlicesIntersectingRange(rangeOfInterest,
                                                   implRenderingSlices);
    }

    var frametimeData = [];
    renderingSlices.sort(function(a, b) {return a.start - b.start});
    for (var i = 1; i < renderingSlices.length; i++) {
      var diff = renderingSlices[i].start - renderingSlices[i - 1].start;
      frametimeData.push({'x': renderingSlices[i].start, 'frametime': diff});
    }
    return frametimeData;
  }

  var UI_COMP_NAME = 'INPUT_EVENT_LATENCY_UI_COMPONENT';
  var ORIGINAL_COMP_NAME = 'INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT';
  var BEGIN_COMP_NAME = 'INPUT_EVENT_LATENCY_BEGIN_RWH_COMPONENT';
  var END_COMP_NAME = 'INPUT_EVENT_LATENCY_TERMINATED_FRAME_SWAP_COMPONENT';

  function getLatencyData(model, rangeOfInterest) {
    var latencySlices = [];
    model.getAllThreads().forEach(function(thread) {
      thread.iterateAllEvents(function(event) {
        if (event.title.indexOf('InputLatency') === 0) {
          latencySlices.push(event);
        }
      });
    });

    latencySlices = getSlicesIntersectingRange(rangeOfInterest,
                                               latencySlices);
    var latencyData = [];
    var latency = 0;
    var averageLatency = 0;

    // Helper function that computes the input latency for one async slice.
    function getLatency(event) {
      if ((!('step' in event.args)) || (!('data' in event.args)))
        return;

      var data = event.args.data;
      if (!(END_COMP_NAME in data))
        return;

      var endTime = data[END_COMP_NAME].time;
      if (ORIGINAL_COMP_NAME in data) {
        latency = endTime - data[ORIGINAL_COMP_NAME].time;
      } else if (UI_COMP_NAME in data) {
        latency = endTime - data[UI_COMP_NAME].time;
      } else if (BEGIN_COMP_NAME in data) {
        latency = endTime - data[BEGIN_COMP_NAME].time;
      } else {
        throw new Error('No valid begin latency component');
      }
      latencyData.push({'x': event.start, 'latency': latency / 1000.0});
    };

    latencySlices.forEach(getLatency);
    latencyData.sort(function(a, b) {return a.x - b.x});
    return latencyData;
  }

  /**
   * @constructor
   */
  var InputLatencySidePanel = tvcm.ui.define('x-input-latency-side-panel',
                                             tracing.TimelineViewSidePanel);
  InputLatencySidePanel.textLabel = 'Input Latency';
  InputLatencySidePanel.supportsModel = function(m) {
    if (m == undefined) {
      return {
        supported: false,
        reason: 'Unknown tracing model'
      };
    }

    if (findBrowserProcess(m) === undefined) {
      return {
        supported: false,
        reason: 'No browser process found'
      };
    }

    var hasLatencyInfo = false;
    m.getAllThreads().forEach(function(thread) {
      thread.iterateAllEvents(function(event) {
        if (event.title.indexOf('InputLatency') === 0)
          hasLatencyInfo = true;
      });
    });

    if (hasLatencyInfo) {
      return {
        supported: true
      };
    }

    return {
      supported: false,
      reason: 'No InputLatency events trace. Consider enableing "benchmark" and "input" category when recording the trace' // @suppress longLineCheck
    };
  };

  InputLatencySidePanel.prototype = {
    __proto__: tracing.TimelineViewSidePanel.prototype,

    decorate: function() {
      tracing.TimelineViewSidePanel.prototype.decorate.call(this);
      this.classList.add('x-input-latency-side-panel');
      this.appendChild(tvcm.instantiateTemplate(
          '#x-input-latency-side-panel-template'));

      this.rangeOfInterest_ = new tvcm.Range();
      this.frametimeType_ = MAIN_FRAMETIME_TYPE;
      this.latencyChart_ = undefined;
      this.frametimeChart_ = undefined;

      var toolbarEl = this.querySelector('toolbar');
      toolbarEl.appendChild(tvcm.ui.createSelector(
          this, 'frametimeType',
          'inputLatencySidePanel.frametimeType', this.frametimeType_,
          [{label: 'Main Thread Frame Times', value: MAIN_FRAMETIME_TYPE},
           {label: 'Impl Thread Frame Times', value: IMPL_FRAMETIME_TYPE}
          ]));
    },

    get model() {
      return this.model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateContents_();
    },

    get frametimeType() {
      return this.frametimeType_;
    },

    set frametimeType(type) {
      if (this.frametimeType_ === type)
        return;
      this.frametimeType_ = type;
      this.updateContents_();
    },

    updateContents_: function() {
      var resultArea = this.querySelector('result-area');
      this.latencyChart_ = undefined;
      this.frametimeChart_ = undefined;
      resultArea.textContent = '';

      if (this.model_ === undefined)
        return;

      var rangeOfInterest;
      if (this.rangeOfInterest_.isEmpty)
        rangeOfInterest = this.model_.bounds;
      else
        rangeOfInterest = this.rangeOfInterest_;


      var frametimeData = getFrametimeData(this.model_, this.frametimeType,
                                           rangeOfInterest);
      var averageFrametime = tvcm.Statistics.mean(frametimeData, function(d) {
        return d.frametime});

      var latencyData = getLatencyData(this.model_, rangeOfInterest);
      var averageLatency = tvcm.Statistics.mean(latencyData, function(d) {
        return d.latency});

      // Create summary.
      var latencySummaryText = document.createElement('div');
      latencySummaryText.appendChild(tvcm.ui.createSpan({
        textContent: 'Average Latency ' + averageLatency + 'ms',
        bold: true}));
      resultArea.appendChild(latencySummaryText);

      var frametimeSummaryText = document.createElement('div');
      frametimeSummaryText.appendChild(tvcm.ui.createSpan({
        textContent: 'Average Frame Time ' + averageFrametime + 'ms',
        bold: true}));
      resultArea.appendChild(frametimeSummaryText);

      if (latencyData.length != 0) {
        this.latencyChart_ = createLatencyLineChart(latencyData,
                                                    'Latency Over Time');
        resultArea.appendChild(this.latencyChart_);
      }

      if (frametimeData.length != 0) {
        this.frametimeChart_ = createLatencyLineChart(frametimeData,
                                                      'Frame Times');
        this.frametimeChart_.style.display = 'block';
        resultArea.appendChild(this.frametimeChart_);
      }
    },

    get rangeOfInterest() {
      return this.rangeOfInterest_;
    },

    set rangeOfInterest(rangeOfInterest) {
      this.rangeOfInterest_ = rangeOfInterest;
      this.updateContents_();
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(InputLatencySidePanel);

  return {
    createLatencyLineChart: createLatencyLineChart,
    getLatencyData: getLatencyData,
    getFrametimeData: getFrametimeData,
    InputLatencySidePanel: InputLatencySidePanel
  };
});
