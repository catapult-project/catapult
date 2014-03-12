// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('telemetry.web_components.ui.pie_chart');

tvcm.testSuite('telemetry.web_components.ui.pie_chart_unittest', function() {
  test('simple', function() {
    var chart = new telemetry.web_components.ui.PieChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value: 100},
      {label: 'b', value: 200},
      {label: 'c', value: 300}
    ];
    chart.data = data;
    this.addHTMLOutput(chart);
  });
});
