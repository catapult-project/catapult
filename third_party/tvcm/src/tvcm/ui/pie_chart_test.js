// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.ui.pie_chart');

tvcm.testSuite('tvcm.ui.pie_chart_test', function() {
  test('simple', function() {
    var chart = new tvcm.ui.PieChart();
    chart.width = 400;
    chart.height = 200;
    assertEquals('400', chart.getAttribute('width'));
    assertEquals('200', chart.getAttribute('height'));
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value: 100},
      {label: 'b', value: 200},
      {label: 'c', value: 300}
    ];
    chart.data = data;
    chart.highlightedLegendKey = 'a';
    chart.pushTempHighlightedLegendKey('b');
    chart.highlightedLegendKey = 'c';
    assertEquals('b', chart.currentHighlightedLegendKey);
    chart.popTempHighlightedLegendKey('b');
    assertEquals('c', chart.highlightedLegendKey);
    this.addHTMLOutput(chart);
  });

  test('withValueText', function() {
    var chart = new tvcm.ui.PieChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value: 100, valueText: '100ms'},
      {label: 'b', value: 200, valueText: '200ms'},
      {label: 'c', value: 300, valueText: '300ms'}
    ];
    chart.data = data;
    this.addHTMLOutput(chart);
  });

  test('lotsOfValues', function() {
    var chart = new tvcm.ui.PieChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {label: 'a', value: 100},
      {label: 'bb', value: 200},
      {label: 'cccc', value: 300},
      {label: 'dd', value: 50},
      {label: 'eeeee', value: 250},
      {label: 'fffffff', value: 120},
      {label: 'ggg', value: 90},
      {label: 'hhhh', value: 175},
      {label: 'iiiiiiiiii', value: 325},
      {label: 'jjjjjj', value: 140},
      {label: 'kkkkkkkkk', value: 170},
      {label: 'lll', value: 220}
    ];
    chart.data = data;
    this.addHTMLOutput(chart);
  });
});
