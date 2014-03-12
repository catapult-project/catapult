// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.range');
tvcm.require('tracing.color_scheme');
tvcm.require('telemetry.web_components.ui.d3');
tvcm.require('telemetry.web_components.ui.chart_base');

tvcm.requireStylesheet('telemetry.web_components.ui.line_chart');

tvcm.exportTo('telemetry.web_components.ui', function() {
  var ChartBase = telemetry.web_components.ui.ChartBase;
  var getColorOfKey = telemetry.web_components.ui.getColorOfKey;

  /**
   * @constructor
   */
  var LineChart = tvcm.ui.define('line-chart', ChartBase);

  LineChart.prototype = {
    __proto__: ChartBase.prototype,

    decorate: function() {
      ChartBase.prototype.decorate.call(this);
      this.classList.add('line-chart');

      this.xScale_ = d3.scale.linear();
      this.yScale_ = d3.scale.linear();
      d3.select(this.chartAreaElement)
          .append('g')
          .attr('id', 'series');
    },

    /**
     * Sets the data array for the object
     *
     * @param {Array} data The data. Each element must be an object, with at
     * least an x property. All other properties become series names in the
     * chart.
     */
    set data(data) {
      if (data.length == 0)
        throw new Error('Data must be nonzero. Pass undefined.');

      var keys;
      if (data !== undefined) {
        var d = data[0];
        if (d.x === undefined)
          throw new Error('Elements must have "x" fields');
        keys = d3.keys(data[0]);
        keys.splice(keys.indexOf('x'), 1);
        if (keys.length == 0)
          throw new Error('Elements must have at least one other field than X');
      } else {
        keys = undefined;
      }
      this.data_ = data;
      this.seriesKeys_ = keys;

      this.updateContents_();
    },

    getLegendKeys_: function() {
      if (this.seriesKeys_ &&
          this.seriesKeys_.length > 1)
        return this.seriesKeys_.slice();
      return [];
    },

    updateScales_: function(width, height) {
      if (this.data_ === undefined)
        return;

      // X.
      this.xScale_.range([0, width]);
      this.xScale_.domain(d3.extent(this.data_, function(d) { return d.x; }));

      // Y.
      var yRange = new tvcm.Range();
      this.data_.forEach(function(d) {
        this.seriesKeys_.forEach(function(k) {
          yRange.addValue(d[k]);
        });
      }, this);

      this.yScale_.range([height, 0]);
      this.yScale_.domain([yRange.min, yRange.max]);
    },

    updateContents_: function() {
      ChartBase.prototype.updateContents_.call(this);
      if (!this.data_)
        return;

      var chartAreaSel = d3.select(this.chartAreaElement);
      var seriesSel = chartAreaSel.select('#series');
      var pathsSel = seriesSel.selectAll('path').data(this.seriesKeys_);
      pathsSel.enter()
          .append('path')
          .attr('class', 'line')
          .style('stroke', function(key) {
            return getColorOfKey(key);
          })
          .attr('d', function(key) {
            var line = d3.svg.line()
              .x(function(d) { return this.xScale_(d.x); }.bind(this))
              .y(function(d) { return this.yScale_(d[key]); }.bind(this));
            return line(this.data_);
          }.bind(this));
      pathsSel.exit().remove();
    }
  };

  return {
    LineChart: LineChart
  };
});
