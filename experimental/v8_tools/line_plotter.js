'use strict';
/**
 * Concrete implementation of Plotter strategy for creating
 * line graphs.
 * @implements {Plotter}
 */
class LinePlotter {
  /**
   * Initalises the chart by computing the scales for the axes and
   * drawing them. It also applies the labels to the graph (axes and
   * graph titles).
   * @param {GraphData} graph Data to be drawn.
   * @param {Object} chart Chart to draw to.
   * @param {Object} chartDimensions Size of the chart.
   */
  initChart_(graph, chart, chartDimensions) {
    this.scaleForXAxis_ = this.createXAxisScale_(graph, chartDimensions);
    this.scaleForYAxis_ = this.createYAxisScale_(graph, chartDimensions);
    this.xAxisGenerator_ = d3.axisBottom(this.scaleForXAxis_);
    this.yAxisGenerator_ = d3.axisLeft(this.scaleForYAxis_);
    // Draw the x-axis.
    chart.append('g')
        .call(this.xAxisGenerator_)
        .attr('transform', `translate(0, ${chartDimensions.height})`);
    this.yAxisDrawing_ = chart.append('g')
        .call(this.yAxisGenerator_);
  }

  createXAxisScale_(graph, chartDimensions) {
    const numDataPoints =
      Math.max(...graph.dataSources.map(source => source.data.length));
    return d3.scaleLinear()
        .domain([0, numDataPoints])
        .range([0, chartDimensions.width]);
  }

  createYAxisScale_(graph, chartDimensions) {
    return d3.scaleLinear()
        .domain([graph.max(point => point), 0])
        .range([0, chartDimensions.height]);
  }

  /**
   * Draws a line plot to the canvas. If there are multiple dataSources it will
   * plot them both and label their colors in the legend.
   * @param {GraphData} graph The data to be plotted.
   * @param {Object} chart d3 selection for the chart element to be drawn on.
   * @param {Object} legend d3 selection for the legend element for
   * additional information to be drawn on.
   * @param {Object} chartDimensions The margins, width and height
   * of the chart. This is useful for computing appropriates axis
   * scales and positioning elements.
   */
  plot(graph, chart, legend, chartDimensions) {
    this.initChart_(graph, chart, chartDimensions);
    const pathGenerator = d3.line()
        .x(datum => this.scaleForXAxis_(datum.x))
        .y(datum => this.scaleForYAxis_(datum.y))
        .curve(d3.curveMonotoneX);

    const dots = graph.process(GraphData.computeCumulativeFrequencies);
    dots.forEach(({ data, color, key }, index) => {
      chart.selectAll('.dot')
          .data(data)
          .enter()
          .append('circle')
          .attr('cx', datum => this.scaleForXAxis_(datum.x))
          .attr('cy', datum => this.scaleForYAxis_(datum.y))
          .attr('r', 3)
          .attr('fill', color)
          .attr('class', 'line-dot')
          .attr('clip-path', 'url(#plot-clip)');
      chart.append('path')
          .datum(data)
          .attr('d', pathGenerator)
          .attr('stroke', color)
          .attr('fill', 'none')
          .attr('stroke-width', 2)
          .attr('data-legend', key)
          .attr('class', 'line-plot')
          .attr('clip-path', 'url(#plot-clip)');
      legend.append('text')
          .text(key)
          .attr('y', index + 'em')
          .attr('fill', color);
    });
    const redraw = (xAxisScale, yAxisScale) => {
      const pathGenerator = d3.line()
          .x(d => this.scaleForXAxis_(d.x))
          .y(d => yAxisScale(d.y))
          .curve(d3.curveMonotoneX);
      chart.selectAll('.line-dot')
          .attr('cx', datum => this.scaleForXAxis_(datum.x))
          .attr('cy', datum => yAxisScale(datum.y));
      chart.selectAll('.line-plot')
          .attr('d', pathGenerator);
    };
    const axes = {
      y: {
        generator: this.yAxisGenerator_,
        drawing: this.yAxisDrawing_,
        scale: this.scaleForYAxis_,
      },
    };
    const shouldScale = {
      x: false,
      y: true,
    };
    GraphUtils.createZoom(shouldScale, chart, chartDimensions, redraw, axes);
  }
}
