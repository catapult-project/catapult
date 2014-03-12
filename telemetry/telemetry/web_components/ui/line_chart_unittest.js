// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('telemetry.web_components.ui.line_chart');

tvcm.testSuite('telemetry.web_components.ui.line_chart_unittest', function() {
  test('singleSeries', function() {
    var chart = new telemetry.web_components.ui.LineChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {x: 10, y: 100},
      {x: 20, y: 110},
      {x: 30, y: 100},
      {x: 40, y: 50}
    ];
    chart.data = data;
    this.addHTMLOutput(chart);
  });

  test('twoSeries', function() {
    var chart = new telemetry.web_components.ui.LineChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {x: 10, value1: 100, value2: 50},
      {x: 20, value1: 110, value2: 75},
      {x: 30, value1: 100, value2: 125},
      {x: 40, value1: 50, value2: 125}
    ];
    chart.data = data;
    this.addHTMLOutput(chart);
  });
});
