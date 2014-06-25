// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.ui.line_chart');

tvcm.testSuite('tvcm.ui.line_chart_test', function() {
  test('singleSeries', function() {
    var chart = new tvcm.ui.LineChart();
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
    var chart = new tvcm.ui.LineChart();

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

    var r = new tvcm.Range();
    r.addValue(20);
    r.addValue(40);
    chart.brushedRange = r;

    this.addHTMLOutput(chart);
  });

  test('interactiveBrushing', function() {
    var chart = new tvcm.ui.LineChart();
    chart.width = 400;
    chart.height = 200;
    chart.chartTitle = 'Chart title';
    var data = [
      {x: 10, value: 50},
      {x: 20, value: 60},
      {x: 30, value: 80},
      {x: 40, value: 20},
      {x: 50, value: 30},
      {x: 60, value: 20},
      {x: 70, value: 15},
      {x: 80, value: 20}
    ];
    chart.data = data;


    var mouseDownIndex = undefined;
    var curMouseIndex = undefined;
    function getSampleWidth(index, leftSide) {
      var leftIndex, rightIndex;
      if (leftSide) {
        leftIndex = Math.max(index - 1, 0);
        rightIndex = index;
      } else {
        leftIndex = index;
        rightIndex = Math.min(index + 1, data.length - 1);
      }
      var leftWidth = data[index].x - data[leftIndex].x;
      var rightWidth = data[rightIndex].x - data[index].x;
      return leftWidth * 0.5 + rightWidth * 0.5;
    }

    function updateBrushedRange() {
      var r = new tvcm.Range();
      if (mouseDownIndex === undefined) {
        chart.brushedRange = r;
        return;
      }
      var leftIndex = Math.min(mouseDownIndex, curMouseIndex);
      var rightIndex = Math.max(mouseDownIndex, curMouseIndex);
      leftIndex = Math.max(0, leftIndex);
      rightIndex = Math.min(data.length - 1, rightIndex);
      r.addValue(data[leftIndex].x - getSampleWidth(leftIndex, true));
      r.addValue(data[rightIndex].x + getSampleWidth(rightIndex, false));
      chart.brushedRange = r;
    }

    chart.addEventListener('item-mousedown', function(e) {
      mouseDownIndex = e.index;
      curMouseIndex = e.index;
      updateBrushedRange();
    });
    chart.addEventListener('item-mousemove', function(e) {
      if (e.button == undefined)
        return;
      curMouseIndex = e.index;
      updateBrushedRange();
    });
    chart.addEventListener('item-mouseup', function(e) {
      curMouseIndex = e.index;
      updateBrushedRange();
    });
    this.addHTMLOutput(chart);
  });
});
