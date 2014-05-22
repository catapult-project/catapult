// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.ui.sunburst_chart');

tvcm.testSuite('tvcm.ui.sunburst_chart_test', function() {
  test('simple', function() {
    var chart = new tvcm.ui.SunburstChart();
    chart.width = 600;
    chart.height = 600;
    assertEquals('600', chart.getAttribute('width'));
    assertEquals('600', chart.getAttribute('height'));
    chart.chartTitle = 'Chart title';
    var data = {
      'comp': 'root',
      'name': '<All Threads>',
      'children': [
        {
          'comp': 'Thread',
          'name': 'Thread 1',
          'children': [
            {
              'comp': 'Chrome',
              'name': 'foo()',
              'children': [
                {
                  'comp': 'Chrome',
                  'name': 'foo()',
                  'size': 150
                },
                {
                  'comp': 'Chrome',
                  'name': 'bar()',
                  'size': 200
                }]
            },
            {
              'comp': 'Chrome',
              'name': 'bar()',
              'size': 200
            }]
        },
        {
          'comp': 'Thread',
          'name': 'Thread 2',
          'children': [
            {
              'comp': 'Java',
              'name': 'Java',
              'size': 100
            }]
        }]
    };
    chart.data = data;
    this.addHTMLOutput(chart);
  });
});
