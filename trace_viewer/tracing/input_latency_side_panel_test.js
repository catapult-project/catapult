// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.importer.trace_event_importer');
tvcm.require('tracing.input_latency_side_panel');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.test_utils');

tvcm.unittest.testSuite('tracing.input_latency_side_panel_test', function() {

  test('getLatencyData', function() {
    var events = [];
    for (var i = 0; i < 10; i++) {
      var start_ts = i * 10000;
      var end_ts = i * 10000 + 1000 * (i % 2);

      // Non Input latency related slices
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'ts' : start_ts, 'ph' : 'S', 'name' : 'Test', 'id' : i}); // @suppress longLineCheck
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'ts' : end_ts, 'ph' : 'F', 'name' : 'Test', 'id' : i}); // @suppress longLineCheck

      // Input latency sclices
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'ts' : start_ts, 'ph' : 'S', 'name' : 'InputLatency', 'id' : i}); // @suppress longLineCheck
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'ts' : end_ts, 'ph' : 'T', 'name' : 'InputLatency', 'args' : {'step' : 'GestureScrollUpdate'}, 'id' : i}); // @suppress longLineCheck
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'ts' : end_ts, 'ph' : 'F', 'name' : 'InputLatency', 'args' : {'data' : {'INPUT_EVENT_LATENCY_ORIGINAL_COMPONENT' : {'time' : start_ts}, 'INPUT_EVENT_LATENCY_TERMINATED_FRAME_SWAP_COMPONENT' : {'time' : end_ts}}}, 'id' : i}); // @suppress longLineCheck
    }

    var m = new tracing.TraceModel(events);
    var latencyData = tracing.getLatencyData(m, m.bounds);
    assertEquals(10, latencyData.length);
    for (var i = 0; i < latencyData.length; i++) {
      assertEquals(i % 2, latencyData[i].latency);
    }
  });

  test('getFrametime', function() {
    var events = [];
    events.push({'cat' : '__metadata', 'pid' : 3507, 'tid' : 3507, 'ts' : 0, 'ph' : 'M', 'name' : 'thread_name', 'args' : {'name' : 'CrBrowserMain'}}); // @suppress longLineCheck
    events.push({'cat' : '__metadata', 'pid' : 3507, 'tid' : 3560, 'ts' : 0, 'ph' : 'M', 'name' : 'thread_name', 'args' : {'name' : 'Chrome_InProcGpuThread'}}); // @suppress longLineCheck

    var frame_ts = 0;
    for (var i = 0; i < 10; i++) {
      events.push({'cat' : 'benchmark', 'pid' : 3507, 'tid' : 3507, 'ts' : frame_ts, 'ph' : 'i', 'name' : 'BenchmarkInstrumentation::MainThreadRenderingStats', 's' : 't'}); // @suppress longLineCheck
      frame_ts += 16000 + 1000 * (i % 2);
    }

    var m = new tracing.TraceModel(events);
    var panel = new tracing.InputLatencySidePanel();
    var frametime_data =
        tracing.getFrametimeData(m, panel.frametimeType, m.bounds);
    assertEquals(9, frametime_data.length);
    for (var i = 0; i < frametime_data.length; i++) {
      assertEquals(16 + i % 2, frametime_data[i].frametime);
    }

  });

  test('basic', function() {
    var latencyData = [
      {
        x: 1000,
        latency: 16
      },
      {
        x: 2000,
        latency: 17
      },
      {
        x: 3000,
        latency: 14
      },
      {
        x: 4000,
        latency: 23
      }
    ];
    var latencyChart = tracing.createLatencyLineChart(latencyData, 'latency');
    this.addHTMLOutput(latencyChart);

    var frametimeData = [
      {
        x: 1000,
        frametime: 16
      },
      {
        x: 2000,
        frametime: 17
      },
      {
        x: 3000,
        frametime: 14
      },
      {
        x: 4000,
        frametime: 23
      }
    ];
    var frametimeChart = tracing.createLatencyLineChart(frametimeData,
                                                        'frametime');
    this.addHTMLOutput(frametimeChart);
  });
});
