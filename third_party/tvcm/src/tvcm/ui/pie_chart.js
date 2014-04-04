// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.range');
tvcm.require('tvcm.ui.d3');
tvcm.require('tvcm.ui.chart_base');

tvcm.requireStylesheet('tvcm.ui.pie_chart');

tvcm.exportTo('tvcm.ui', function() {
  var ChartBase = tvcm.ui.ChartBase;
  var getColorOfKey = tvcm.ui.getColorOfKey;

  /**
   * @constructor
   */
  var PieChart = tvcm.ui.define('pie-chart', ChartBase);

  PieChart.prototype = {
    __proto__: ChartBase.prototype,

    decorate: function() {
      ChartBase.prototype.decorate.call(this);
      this.classList.add('pie-chart');

      this.data_ = undefined;
      this.seriesKeys_ = undefined;

      var chartAreaSel = d3.select(this.chartAreaElement);
      this.pieGroup_ = chartAreaSel.append('g')
        .attr('class', 'pie-group')
        .node();
    },

    get data() {
      return this.data_;
    },


    /**
     * @param {Array} data Data for the chart, where each element in the array
     * must be of the form {label: str, value: number}.
     */
    set data(data) {
      if (data !== undefined) {
        // Figure out the label values in the data set. E.g. from
        //   [{label: 'a', ...}, {label: 'b', ...}]
        // we would commpute ['a', 'y']. These become the series keys.
        var seriesKeys = [];
        var seenSeriesKeys = {};
        data.forEach(function(d) {
          var k = d.label;
          if (seenSeriesKeys[k])
            throw new Error('Label ' + k + ' has been used already');
          seriesKeys.push(k);
          seenSeriesKeys[k] = true;
        }, this);
        this.seriesKeys_ = seriesKeys;
      } else {
        this.seriesKeys_ = undefined;
      }
      this.data_ = data;
      this.updateContents_();
    },

    getLegendKeys_: function() {
      if (this.data_ === undefined)
        return [];
      return this.seriesKeys_;
    },

    updateScales_: function(width, height) {
      if (this.data_ === undefined)
        return;
    },

    updateContents_: function() {
      ChartBase.prototype.updateContents_.call(this);
      if (!this.data_)
        return;

      var width = this.chartAreaSize.width;
      var height = this.chartAreaSize.height;
      var radius = Math.min(width, height) / 2;

      var pieGroupSel = d3.select(this.pieGroup_);
      pieGroupSel.attr('transform',
                       'translate(' + width / 2 + ',' + height / 2 + ')');

      // Bind the pie layout to its data
      var pieLayout = d3.layout.pie()
        .value(function(d) { return d.value; })
        .sort(null);

      var piePathsSel = pieGroupSel.datum(this.data_).selectAll('path')
        .data(pieLayout);


      var arcRenderer = d3.svg.arc()
        .innerRadius(0)
        .outerRadius(radius - 20);
      piePathsSel.enter().append('path')
        .attr('class', 'arc')
        .attr('fill', function(d, i) {
            var origData = this.data_[i];
            var highlighted = (origData.label ===
                               this.currentHighlightedLegendKey);
            return getColorOfKey(origData.label, highlighted);
          }.bind(this))
        .attr('d', arcRenderer)
        .on('click', function(d, i) {
            var origData = this.data_[i];
            if (origData.onClick)
              origData.onClick(d, i);
            d3.event.stopPropagation();
          }.bind(this))
        .on('mouseenter', function(d, i) {
            var origData = this.data_[i];
            this.pushTempHighlightedLegendKey(origData.label);
          }.bind(this))
        .on('mouseleave', function(d, i) {
            var origData = this.data_[i];
            this.popTempHighlightedLegendKey(origData.label);
          }.bind(this));

      piePathsSel.enter().append('text')
        .attr('class', 'arc-text')
        .attr('transform', function(d) {
            return 'translate(' + arcRenderer.centroid(d) + ')';
          })
        .attr('dy', '.35em')
        .style('text-anchor', 'middle')
        .text(function(d, i) {
            var origData = this.data_[i];
            if (origData.valueText)
              return origData.valueText;
            return '';
          }.bind(this));

      piePathsSel.exit().remove();
    },

    updateHighlight_: function() {
      ChartBase.prototype.updateHighlight_.call(this);
      // Update color of pie segments.
      var pieGroupSel = d3.select(this.pieGroup_);
      var that = this;
      pieGroupSel.selectAll('.arc').each(function(d, i) {
        var origData = that.data_[i];
        var highlighted = origData.label == that.currentHighlightedLegendKey;
        var color = getColorOfKey(origData.label, highlighted);
        this.style.fill = color;
      });
    }
  };

  return {
    PieChart: PieChart
  };
});
