// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.time_summary_side_panel');
tvcm.require('tracing.trace_model');
tvcm.require('tracing.test_utils');

tvcm.unittest.testSuite('tracing.time_summary_side_panel_test', function() {
  var newSliceNamed = tracing.test_utils.newSliceNamed;

  function createModel() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      var browserProcess = m.getOrCreateProcess(1);
      var browserMain = browserProcess.getOrCreateThread(2);
      browserMain.name = 'CrBrowserMain';
      browserMain.sliceGroup.beginSlice('cat', 'Task', 0, undefined, 0);
      browserMain.sliceGroup.endSlice(10, 9);
      browserMain.sliceGroup.beginSlice('cat', 'Task', 20, undefined, 10);
      browserMain.sliceGroup.endSlice(30, 20);

      var rendererProcess = m.getOrCreateProcess(4);
      var rendererMain = rendererProcess.getOrCreateThread(5);
      rendererMain.name = 'CrRendererMain';
      rendererMain.sliceGroup.beginSlice('cat', 'Task', 0, undefined, 0);
      rendererMain.sliceGroup.endSlice(30, 25);
      rendererMain.sliceGroup.beginSlice('cat', 'Task', 40, undefined, 40);
      rendererMain.sliceGroup.endSlice(60, 50);
    });
    return m;
  }

  test('group', function() {
    var m = createModel();
    var group = new tracing.ResultsForGroup(m, 'foo');
    group.appendThreadSlices(m.bounds, m.processes[1].threads[2]);
    assertEquals(20, group.wallTime);
    assertEquals(19, group.cpuTime);
  });

  test('trim', function() {
    var groupData = [
      {
        value: 2.854999999999997,
        label: '156959'
      },
      {
        value: 9.948999999999998,
        label: '16131'
      },
      {
        value: 42.314000000000725,
        label: '51511'
      },
      {
        value: 31.06900000000028,
        label: 'AudioOutputDevice'
      },
      {
        value: 1.418,
        label: 'BrowserBlockingWorker2/50951'
      },
      {
        value: 0.044,
        label: 'BrowserBlockingWorker3/50695'
      },
      {
        value: 18.52599999999993,
        label: 'Chrome_ChildIOThread'
      },
      {
        value: 2.888,
        label: 'Chrome_FileThread'
      },
      {
        value: 0.067,
        label: 'Chrome_HistoryThread'
      },
      {
        value: 25.421000000000046,
        label: 'Chrome_IOThread'
      },
      {
        value: 0.019,
        label: 'Chrome_ProcessLauncherThread'
      },
      {
        value: 643.087999999995,
        label: 'Compositor'
      },
      {
        value: 4.049999999999973,
        label: 'CompositorRasterWorker1/22031'
      },
      {
        value: 50.040000000000106,
        label: 'CrBrowserMain'
      },
      {
        value: 1256.5130000000042,
        label: 'CrGpuMain'
      },
      {
        value: 5502.19499999999,
        label: 'CrRendererMain'
      },
      {
        value: 15.552999999999862,
        label: 'FFmpegDemuxer'
      },
      {
        value: 63.706000000001524,
        label: 'Media'
      },
      {
        value: 2.7419999999999987,
        label: 'PowerSaveBlocker'
      },
      {
        value: 0.11500000000000005,
        label: 'Watchdog'
      }
    ];

    var groups = [];
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      var start = 0;
      groupData.forEach(function(groupData) {
        var group = new tracing.ResultsForGroup(m, groupData.label);

        var slice = newSliceNamed(groupData.label, start, groupData.value);
        start += groupData.value;
        group.allSlices.push(slice);
        group.topLevelSlices.push(slice);

        groups.push(group);
      });
    });


    function getValueFromGroup(d) { return d.wallTime; }

    var otherGroup = new tracing.ResultsForGroup(m, 'Other');
    var newGroups = tracing.trimPieChartData(
        groups, otherGroup, getValueFromGroup);

    // Visualize the data once its trimmed.
    var chart = tracing.createPieChartFromResultGroups(
        newGroups, 'Trimmed', getValueFromGroup);
    this.addHTMLOutput(chart);
    chart.setSize(chart.getMinSize());
  });


  test('basic', function() {
    var m = createModel();
    assertTrue(tracing.TimeSummarySidePanel.supportsModel(m).supported);

    var panel = new tracing.TimeSummarySidePanel();
    this.addHTMLOutput(panel);
    panel.model = m;
    panel.style.border = '1px solid black';
  });
});
