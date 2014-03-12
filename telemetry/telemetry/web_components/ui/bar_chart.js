// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.range');
tvcm.require('tracing.color_scheme');
tvcm.require('telemetry.web_components.ui.d3');
tvcm.require('telemetry.web_components.ui.chart_base');

tvcm.requireStylesheet('telemetry.web_components.ui.bar_chart');

tvcm.exportTo('telemetry.web_components.ui', function() {
  var ChartBase = telemetry.web_components.ui.ChartBase;
  var getColorOfKey = telemetry.web_components.ui.getColorOfKey;

  /**
   * @constructor
   */
  var BarChart = tvcm.ui.define('bar-chart', ChartBase);

  BarChart.prototype = {
    __proto__: ChartBase.prototype,

    decorate: function() {
      ChartBase.prototype.decorate.call(this);
      this.classList.add('bar-chart');

      this.xScale_ = undefined;
      this.xSubScale_ = undefined;
      this.yScale_ = undefined;

      this.data_ = undefined;
      this.xLabelValues_ = undefined;
      this.xLabelKey_ = undefined;
      this.seriesKeys_ = undefined;
    },

    get data() {
      return this.data_;
    },

    get xLabelKey() {
      return this.xLabelKey_;
    },

    setDataAndXLabelKey: function(data, xLabelKey) {
      if (data !== undefined) {
        // Figure out what the series keys are. E.g. for {label: 'a', value1: 3,
        // value2: 4} compute ['value1', 'value2'].
        var seriesKeys = [];
        d3.keys(data[0]).forEach(function(k) {
          if (k == xLabelKey)
            return;
          seriesKeys.push(k);
        });

        // Figure out the x labels in the data set. E.g. from
        //   [{label: 'a', ...}, {label: 'b', ...}]
        // we would commpute ['a', 'y'].
        var xLabelValues = [];
        var seenXLabelValues = {};
        data.forEach(function(d) {
          var xLabelValue = d[xLabelKey];
          if (seenXLabelValues[xLabelValue])
            throw new Error('Label ' + xLabelValue + ' has been used already');
          xLabelValues.push(xLabelValue);
          seenXLabelValues[xLabelValue] = true;
        }, this);
        this.xLabelKey_ = xLabelKey;
        this.seriesKeys_ = seriesKeys;
        this.xLabelValues_ = xLabelValues;
      } else {
        this.xLabelKey_ = undefined;
        this.seriesKeys_ = undefined;
        this.xLabelValues_ = undefined;
      }
      this.data_ = data;
      this.updateContents_();
    },

    getLegendKeys_: function() {
      if (this.seriesKeys_ &&
          this.seriesKeys_.length > 1)
        return this.seriesKeys_.slice();
      return [];
    },

    updateScales_: function(width, height) {
      if (this.data_ === undefined) {
        this.xScale_ = undefined;
        this.xSubScale_ = undefined;
        this.yScale_ = undefined;
        return;
      }

      // xScale maps x labels to a position in the overall timeline.
      this.xScale_ = d3.scale.ordinal();
      this.xScale_.rangeRoundBands([0, width], .1);
      this.xScale_.domain(this.xLabelValues_);

      // xSubScale maps an individual series to a position within its group
      // of related bars.
      this.xSubScale_ = d3.scale.ordinal();
      this.xSubScale_.domain(this.seriesKeys_)
          .rangeRoundBands([0, this.xScale_.rangeBand()]);

      // Regular mapping of values to the full chart height.
      var yRange = new tvcm.Range();
      this.data_.forEach(function(d) {
        this.seriesKeys_.forEach(function(k) {
          yRange.addValue(d[k]);
        }, this);
      }, this);
      this.yScale_ = d3.scale.linear();
      this.yScale_.range([height, 0]);

      this.yScale_.domain([yRange.min, yRange.max]);
    },

    updateContents_: function() {
      ChartBase.prototype.updateContents_.call(this);
      if (!this.data_)
        return;

      var width = this.chartAreaSize.width;
      var height = this.chartAreaSize.height;

      var chartAreaSel = d3.select(this.chartAreaElement);

      // An index-group has the rects from the same array index in the source
      // data set.
      var indexGroupSel = chartAreaSel.selectAll('.index-group')
          .data(this.data_);
      indexGroupSel.enter().append('g')
          .attr('class', '.index-group')
          .attr('transform', function(d) {
            var k = d[this.xLabelKey_];
            return 'translate(' + this.xScale_(k) + ',0)';
          }.bind(this));
      indexGroupSel.exit().remove();

      // Within an index group, create a rect for each actual value.
      var rectsSel = indexGroupSel.selectAll('rect')
        .data(function(d) {
            // 'd' is an index in the original array. We want to extract out the
            // actual values from it from this.seriesKeys_. This we turn into
            // {name: seriesKey, value: d[seriesKey]} objects that then get
            // data-bound to each rect.
            var values = [];
            for (var i = 0; i < this.seriesKeys_.length; i++) {
              var k = this.seriesKeys_[i];
              values.push({name: k,
                           value: d[k]});
            }
            return values;
          }.bind(this));

      rectsSel.enter().append('rect')
        .attr('width', this.xSubScale_.rangeBand())
        .attr('x', function(d) {
            return this.xSubScale_(d.name);
          }.bind(this))
        .attr('y', function(d) {
            return this.yScale_(d.value);
          }.bind(this))
        .attr('height', function(d) {
            return height - this.yScale_(d.value);
          }.bind(this))
        .style('fill', function(d) {
            return getColorOfKey(d.name);
          });
    }
  };

  return {
    BarChart: BarChart
  };
});
