'use strict';

/**
 * Plots the supplied GraphData to the screen.
 */
class GraphPlotter {
  /** @param {DataGraph} graph */
  constructor(graph) {
    if (!(graph instanceof GraphData)) {
      throw new TypeError(
          `A GraphData object must be supplied. Received: ${typeof graph}`);
    }
    /** @private @const {GraphData} */
    this.graph_ = graph;
    /** @private @const {Object} margins Creates room for labels and axis. */
    this.margins_ = {
      top: 15,
      right: 200,
      left: 80,
      bottom: 50
    };
    /** @private {number} */
    this.canvasHeight_ = 400;
    /** @private {number} */
    this.canvasWidth_ = 750;
    /** @private {number} */
    this.chartWidth_ =
      this.canvasWidth_ - this.margins_.left - this.margins_.right;
    /** @private {number} */
    this.chartHeight_ =
      this.canvasHeight_ - this.margins_.top - this.margins_.bottom;
    /** @private {Object} */
    this.background_ = d3.select('#canvas').append('svg:svg')
        .attr('width', this.canvasWidth_)
        .attr('height', this.canvasHeight_);
    /** @private {Object} */
    this.chart_ = this.background_.append('g')
        .attr('transform', `translate(${this.margins_.left}, 
                  ${this.margins_.top})`);
    /** @private {Object} */
    this.legend_ = this.createLegend_();
    /** @private {Object} */
    this.scaleForXAxis_ = this.setXAxisScale_();
    /** @private {Object} */
    this.scaleForYAxis_ = this.setYAxisScale_();
    /** @private {Object} */
    this.createAxis_();
    /** @private {Object} */
    this.labelAxis_();
  }

  setXAxisScale_() {
    return d3.scaleLinear()
        .domain([0, this.graph_.xAxisMax()])
        .range([0, this.chartWidth_]);
  }

  setYAxisScale_() {
    return d3.scaleLinear()
        .domain([this.graph_.yAxisMax(), 0])
        .range([0, this.chartHeight_]);
  }

  createLegend_() {
    return this.chart_.append('g')
        .attr('class', 'legend')
        .attr('transform',
            `translate(${this.chartWidth_}, ${this.margins_.top})`);
  }

  createAxis_() {
    this.chart_.append('g')
        .call(d3.axisBottom(this.scaleForXAxis_))
        .attr('transform', `translate(0, ${this.chartHeight_})`);

    this.chart_.append('g')
        .call(d3.axisLeft(this.scaleForYAxis_));
  }

  labelAxis_() {
    this.chart_.append('text')
        .attr('transform', `translate(${this.chartWidth_ / 2}, 
            ${this.canvasHeight_ - this.margins_.bottom / 2})`)
        .attr('text-anchor', 'middle')
        .text(this.graph_.xAxis());

    this.chart_.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - (this.margins_.left / 2))
        .attr('x', 0 - (this.chartHeight_ / 2))
        .attr('text-anchor', 'middle')
        .text(this.graph_.yAxis());
  }

  /**
   * Draws a line plot to the canvas. If there are multiple dataSources it will
   * plot them both and label their colors in the legend.
   */
  linePlot() {
    const lineF = d3.line()
        .x(datum => this.scaleForXAxis_(datum.x))
        .y(datum => this.scaleForYAxis_(datum.y))
        .curve(d3.curveMonotoneX);

    this.graph_.dataSources.forEach(({ data, color, key }, index) => {
      this.chart_.selectAll('.dot')
          .data(data)
          .enter()
          .append('circle')
          .attr('cx', datum => this.scaleForXAxis_(datum.x))
          .attr('cy', datum => this.scaleForYAxis_(datum.y))
          .attr('r', 3)
          .attr('fill', color);
      this.chart_.append('path')
          .datum(data)
          .attr('d', lineF)
          .attr('stroke', color)
          .attr('fill', 'none')
          .attr('stroke-width', 2)
          .attr('data-legend', key);
      this.legend_.append('text')
          .text(key)
          .attr('y', index + 'em')
          .attr('fill', color);
    });
  }
}
