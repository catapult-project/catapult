// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tvcm.range');
tvcm.require('tvcm.ui.d3');
tvcm.require('tvcm.ui.dom_helpers');
tvcm.require('tvcm.ui.chart_base');

tvcm.requireStylesheet('tvcm.ui.sunburst_chart');

tvcm.exportTo('tvcm.ui', function() {
  var ChartBase = tvcm.ui.ChartBase;
  var getColorOfKey = tvcm.ui.getColorOfKey;

  var MIN_RADIUS = 100;

  /**
   * @constructor
   */
  var SunburstChart = tvcm.ui.define('sunburst-chart', ChartBase);

  SunburstChart.prototype = {
    __proto__: ChartBase.prototype,

    decorate: function() {
      ChartBase.prototype.decorate.call(this);
      this.classList.add('sunburst-chart');

      this.data_ = undefined;
      this.seriesKeys_ = undefined;

      var chartAreaSel = d3.select(this.chartAreaElement);
      var pieGroupSel = chartAreaSel.append('g')
        .attr('class', 'pie-group');
      this.pieGroup_ = pieGroupSel.node();

      this.backSel_ = pieGroupSel.append('g');

      this.pathsGroup_ = pieGroupSel.append('g')
        .attr('class', 'paths')
        .node();
    },

    get data() {
      return this.data_;
    },


    /**
     * @param {Data} Data for the chart, where data must be of the
     * form {category: str, name: str, (size: number or children: [])} .
     */
    set data(data) {
      this.data_ = data;
      this.updateContents_();
    },

    get margin() {
      var margin = {top: 0, right: 0, bottom: 0, left: 0};
      if (this.chartTitle_)
        margin.top += 40;
      return margin;
    },

    getMinSize: function() {
      if (!tvcm.ui.isElementAttachedToDocument(this))
        throw new Error('Cannot measure when unattached');
      this.updateContents_();

      var titleWidth = this.querySelector(
          '#title').getBoundingClientRect().width;
      var margin = this.margin;
      var marginWidth = margin.left + margin.right;
      var marginHeight = margin.top + margin.bottom;

      // TODO(vmiura): Calc this when we're done with layout.
      return {
        width: 600,
        height: 600
      };
    },

    getLegendKeys_: function() {
      // This class creates its own legend, instead of using ChartBase.
      return undefined;
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
      var radius = Math.max(MIN_RADIUS, Math.min(width, height) / 2);

      d3.select(this.pieGroup_).attr(
          'transform',
          'translate(' + width / 2 + ',' + height / 2 + ')');


      /////////////////////////////////////////
      // Mapping of step names to colors.
      var colors = {
        'Chrome': '#5687d1',
        'Kernel': '#7b615c',
        'GPU Driver': '#ff0000',
        'Java': '#de783b',
        'Android': '#6ab975',
        'Thread': '#aaaaaa',
        'Standard Lib': '#bbbbbb',
        '<self>': '#888888',
        '<unknown>': '#444444'
      };

      // temp test data
      var json = this.data_;
      var partition = d3.layout.partition()
          .size([1, 1]) // radius * radius
          .value(function(d) { return d.size; });

      // For efficiency, filter nodes to keep only those large enough to see.
      var nodes = partition.nodes(json);
      nodes.forEach(function f(d, i) { d.id = i; });
      var totalSize = nodes[0].value;
      var depth = 1.0 + d3.max(nodes, function(d) { return d.depth; });
      var yDomainMin = 1.0 / depth;
      var yDomainMax = Math.min(Math.max(depth, 20), 50) / depth;

      var x = d3.scale.linear()
          .range([0, 2 * Math.PI]);

      var y = d3.scale.sqrt()
          .domain([yDomainMin, yDomainMax])
          .range([50, radius]);

      var arc = d3.svg.arc()
          .startAngle(function(d) {
            return Math.max(0, Math.min(2 * Math.PI, x(d.x)));
          })
          .endAngle(function(d) {
            return Math.max(0, Math.min(2 * Math.PI, x(d.x + d.dx)));
          })
          .innerRadius(function(d) { return Math.max(0, y((d.y))); })
          .outerRadius(function(d) { return Math.max(0, y((d.y + d.dy))); });

      // Interpolate the scales!
      function arcTween(minX, maxX, minY) {
        var xd, yd, yr;

        if (minY > 0) {
          xd = d3.interpolate(x.domain(), [minX, maxX]);
          yd = d3.interpolate(y.domain(), [minY, yDomainMax]);
          yr = d3.interpolate(y.range(), [50, radius]);
        }
        else {
          xd = d3.interpolate(x.domain(), [minX, maxX]);
          yd = d3.interpolate(y.domain(), [yDomainMin, yDomainMax]);
          yr = d3.interpolate(y.range(), [50, radius]);
        }

        return function(d, i) {
          return i ? function(t) { return arc(d); }
              : function(t) {
                x.domain(xd(t)); y.domain(yd(t)).range(yr(t)); return arc(d);
              };
        };
      }


      var clickedNode = null;
      var click_stack = new Array();
      click_stack.push(0);

      function zoomout(d) {
        if (click_stack.length > 1)
          click_stack.pop();
        zoomto(click_stack[click_stack.length - 1]);
      }

      // Bounding circle underneath the sunburst, to make it easier to detect
      // when the mouse leaves the parent g.
      this.backSel_.append('svg:circle')
          .attr('r', radius)
          .style('opacity', 0.0)
          .on('click', zoomout);


      var vis = d3.select(this.pathsGroup_);

      function getNode(id) {
        for (var i = 0; i < nodes.length; i++) {
          if (nodes[i].id == id)
            return nodes[i];
        }
        return null;
      }

      var minX = 0.0;
      var maxX = 1.0;
      var minY = 0.0;
      var clickedY = 0;

      function zoomto(id) {
        var d = getNode(id);

        if (d) {
          clickedY = d.y;
          minX = d.x;
          maxX = d.x + d.dx;
          minY = d.y;
        }
        else {
          clickedY = -1;
          minX = 0.0;
          maxX = 1.0;
          minY = 0.0;
        }

        clickedNode = d;
        redraw(minX, maxX, minY);
        var path = vis.selectAll('path');

        path.transition()
          .duration(750)
          .attrTween('d', arcTween(minX, maxX, minY));

        showBreadcrumbs(d);
      }

      function click(d) {
        if (d3.event.shiftKey) {
          // Zoom partially onto the selected range
          var diff_x = (maxX - minX) * 0.5;
          minX = d.x + d.dx * 0.5 - diff_x * 0.5;
          minX = minX < 0.0 ? 0.0 : minX;
          maxX = minX + diff_x;
          maxX = maxX > 1.0 ? 1.0 : maxX;
          minX = maxX - diff_x;

          redraw(minX, maxX, minY);

          var path = vis.selectAll('path');

          clickedNode = d;
          path.transition()
            .duration(750)
            .attrTween('d', arcTween(minX, maxX, minY));

          return;
        }

        if (click_stack[click_stack.length - 1] != d.id) {
          click_stack.push(d.id);
          zoomto(d.id);
        }
      }

      // Given a node in a partition layout, return an array of all of its
      // ancestor nodes, highest first, but excluding the root.
      function getAncestors(node) {
        var path = [];
        var current = node;
        while (current.parent) {
          path.unshift(current);
          current = current.parent;
        }
        return path;
      }

      function showBreadcrumbs(d) {
        var sequenceArray = getAncestors(d);

        // Fade all the segments.
        vis.selectAll('path')
          .style('opacity', 0.7);

        // Then highlight only those that are an ancestor of the current
        // segment.
        vis.selectAll('path')
          .filter(function(node) {
              return (sequenceArray.indexOf(node) >= 0);
            })
          .style('opacity', 1);
      }

      function mouseover(d) {
        showBreadcrumbs(d);
      }

      // Restore everything to full opacity when moving off the
      // visualization.
      function mouseleave(d) {
        // Hide the breadcrumb trail
        if (clickedNode != null)
          showBreadcrumbs(clickedNode);
        else {
          // Deactivate all segments during transition.
          vis.selectAll('path')
            .on('mouseover', null);

          // Transition each segment to full opacity and then reactivate it.
          vis.selectAll('path')
            .transition()
            .duration(300)
            .style('opacity', 1)
            .each('end', function() {
                d3.select(this).on('mouseover', mouseover);
              });
        }
      }

      // Update visible segments between new min/max ranges.
      function redraw(minX, maxX, minY) {
        var scale = maxX - minX;
        var visible_nodes = nodes.filter(function(d) {
          return d.depth &&
              (d.y >= minY) &&
              (d.x < maxX) &&
              (d.x + d.dx > minX) &&
              (d.dx / scale > 0.001);
        });
        var path = vis.data([json]).selectAll('path')
          .data(visible_nodes, function(d) { return d.id; });

        path.enter().insert('svg:path')
          .attr('d', arc)
          .attr('fill-rule', 'evenodd')
          .style('fill', function(dd) { return colors[dd.category]; })
          .style('opacity', 0.7)
          .on('mouseover', mouseover)
          .on('click', click);

        path.exit().remove();
        return path;
      }

      zoomto(0);
      vis.on('mouseleave', mouseleave);
    },

    updateHighlight_: function() {
      ChartBase.prototype.updateHighlight_.call(this);
      // Update color of pie segments.
      var pathsGroupSel = d3.select(this.pathsGroup_);
      var that = this;
      pathsGroupSel.selectAll('.arc').each(function(d, i) {
        var origData = that.data_[i];
        var highlighted = origData.label == that.currentHighlightedLegendKey;
        var color = getColorOfKey(origData.label, highlighted);
        this.style.fill = color;
      });
    }
  };

  return {
    SunburstChart: SunburstChart
  };
});
