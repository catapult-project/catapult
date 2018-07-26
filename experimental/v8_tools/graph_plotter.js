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
      top: 50,
      right: 200,
      left: 80,
      bottom: 50,
    };
    /** @private {number} */
    this.canvasHeight_ = 720;
    /** @private {number} */
    this.canvasWidth_ = 1280;
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
    // Appending a clip path rectangle prevents any drawings with the
    // clip-path: url(#plot-clip) attribute from being displayed outside
    // of the chart area.
    this.chart_.append('defs')
        .append('clipPath')
        .attr('id', 'plot-clip')
        .append('rect')
        .attr('width', this.chartWidth_)
        .attr('height', this.chartHeight_);
    /** @private {Object} */
    this.legend_ = this.createLegend_();
    // The following properties are intialialised when initChart is called
    // because they rely upon graph data having sufficient information
    // for plotting. Hence it does not make sense to initalise them until
    // plotting is required.
    /** @private {Object} */
    this.scaleForXAxis_ = undefined;
    /** @private {Object} */
    this.scaleForYAxis_ = undefined;
    /** @private {Object} */
    this.xAxisGenerator_ = undefined;
    /** @private {Object} */
    this.yAxisGenerator_ = undefined;
    /** @private {Object} Keep a reference to y-axis for updating on zoom */
    this.yAxisDrawing_ = undefined;
  }

  /**
   * Initalises the chart by computing the scales for the axis and
   * drawing them. It also applies the labels to the graph (axis and
   * graph titles).
   */
  initChart_() {
    this.scaleForXAxis_ = this.createXAxisScale_();
    this.scaleForYAxis_ = this.createYAxisScale_();
    this.xAxisGenerator_ = d3.axisBottom(this.scaleForXAxis_);
    this.yAxisGenerator_ = d3.axisLeft(this.scaleForYAxis_);
    // Draw the x-axis.
    this.chart_.append('g')
        .call(this.xAxisGenerator_)
        .attr('transform', `translate(0, ${this.chartHeight_})`);
    this.yAxisDrawing_ = this.chart_.append('g')
        .call(this.yAxisGenerator_);
    this.labelAxis_();
    this.labelTitle_();
  }

  createXAxisScale_() {
    return d3.scaleLinear()
        .domain([0, this.graph_.xAxisMax()])
        .range([0, this.chartWidth_]);
  }

  createYAxisScale_() {
    return d3.scaleLinear()
        .domain([this.graph_.yAxisMax(), 0])
        .range([0, this.chartHeight_]);
  }

  createLegend_() {
    const padding = 5;
    return this.chart_.append('g')
        .attr('class', 'legend')
        .attr('transform',
            `translate(${this.chartWidth_ + padding}, ${this.margins_.top})`);
  }

  labelAxis_() {
    this.chart_.append('text')
        .attr('transform', `translate(${this.chartWidth_ / 2}, 
            ${this.chartHeight_ + this.margins_.bottom})`)
        .attr('text-anchor', 'middle')
        .text(this.graph_.xAxis());

    this.chart_.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - (this.margins_.left / 2))
        .attr('x', 0 - (this.chartHeight_ / 2))
        .attr('text-anchor', 'middle')
        .text(this.graph_.yAxis());
  }

  labelTitle_() {
    this.chart_.append('text')
        .attr('x', this.chartWidth_ / 2)
        .attr('y', 0 - this.margins_.top / 2)
        .attr('text-anchor', 'middle')
        .text(this.graph_.title());
  }

  /**
   * Draws a line plot to the canvas. If there are multiple dataSources it will
   * plot them both and label their colors in the legend.
   */
  linePlot() {
    this.initChart_();
    const pathGenerator = d3.line()
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
          .attr('fill', color)
          .attr('class', 'line-dot')
          .attr('clip-path', 'url(#plot-clip)');
      this.chart_.append('path')
          .datum(data)
          .attr('d', pathGenerator)
          .attr('stroke', color)
          .attr('fill', 'none')
          .attr('stroke-width', 2)
          .attr('data-legend', key)
          .attr('class', 'line-plot')
          .attr('clip-path', 'url(#plot-clip)');
      this.legend_.append('text')
          .text(key)
          .attr('y', index + 'em')
          .attr('fill', color);
    });
    const zoom = d3.zoom();
    this.setUpZoom_(zoom);
    this.setUpZoomReset_(zoom);
  }

  transformLinePlot_(yAxisScale) {
    const pathGenerator = d3.line()
        .x(d => this.scaleForXAxis_(d.x))
        .y(d => yAxisScale(d.y))
        .curve(d3.curveMonotoneX);
    this.yAxisGenerator_.scale(yAxisScale);
    this.yAxisDrawing_.call(this.yAxisGenerator_);
    this.chart_.selectAll('.line-dot')
        .attr('cx', datum => this.scaleForXAxis_(datum.x))
        .attr('cy', datum => yAxisScale(datum.y));
    this.chart_.selectAll('.line-plot')
        .attr('d', pathGenerator);
  }

  setUpZoom_(zoom) {
    const onZoom = () => {
      const transform = d3.event.transform;
      const transformedScaleForYAxis = transform.rescaleY(this.scaleForYAxis_);
      this.transformLinePlot_(transformedScaleForYAxis);
    };
    zoom.on('zoom', onZoom).scaleExtent([1, Infinity]);
    // The following invisible rectangle is there just to catch
    // mouse events for zooming. It's not possible to listen on
    // the chart itself because it is a g element (which does not
    // capture mouse events).
    this.chart_.append('rect')
        .attr('width', this.chartWidth_)
        .attr('height', this.chartHeight_)
        .attr('class', 'zoom-listener')
        .style('opacity', 0)
        .call(zoom);
  }

  setUpZoomReset_(zoom) {
    // Gives some padding between the x-axis and the reset button.
    const padding = 10;
    const resetButton = this.chart_.append('svg')
        .attr('width', '10em')
        .attr('height', '2em')
        .attr('x', `${this.chartWidth_ + padding}px`)
        .attr('y', `${this.chartHeight_}px`)
        .attr('cursor', 'pointer');
    // Styling for the button.
    resetButton.append('rect')
        .attr('rx', '5px')
        .attr('ry', '5px')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('fill', '#1b39a8');
    resetButton.append('text')
        .text('RESET CHART')
        .attr('x', '50%')
        .attr('y', '50%')
        .attr('fill', 'white')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle');
    resetButton
        .on('mouseover', () => {
          resetButton.attr('opacity', '0.5');
        })
        .on('mouseout', () => {
          resetButton.attr('opacity', '1');
        })
        .on('click', () => {
          resetButton.attr('opacity', '1');
          this.chart_.select('.zoom-listener')
              .call(zoom.transform, d3.zoomIdentity);
          this.transformLinePlot_(this.scaleForYAxis_);
        });
  }
}
