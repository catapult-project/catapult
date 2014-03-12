// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('telemetry.web_components.ui.bar_chart');

tvcm.testSuite('telemetry.web_components.ui.bar_chart_unittest', function() {
  test('singleSeries', function() {
    var chart = new telemetry.web_components.ui.BarChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value: 100},
      {label: 'b', value: 40},
      {label: 'c', value: 20}
    ];
    chart.setDataAndXLabelKey(data, 'label');
    this.addHTMLOutput(chart);
  });

  test('twoSeries', function() {
    var chart = new telemetry.web_components.ui.BarChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value1: 100, value2: 50},
      {label: 'b', value1: 75, value2: 10},
      {label: 'c', value1: 50, value2: 125}
    ];
    chart.setDataAndXLabelKey(data, 'label');
    this.addHTMLOutput(chart);
  });
});
