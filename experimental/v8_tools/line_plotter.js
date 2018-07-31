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
    return d3.scaleLinear()
        .domain([0, graph.xAxisMax()])
        .range([0, chartDimensions.width]);
  }

  createYAxisScale_(graph, chartDimensions) {
    return d3.scaleLinear()
        .domain([graph.yAxisMax(), 0])
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

    graph.dataSources.forEach(({ data, color, key }, index) => {
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
    const zoom = d3.zoom();
    this.setUpZoom_(zoom, chart, chartDimensions);
    this.setUpZoomReset_(zoom, chart, chartDimensions);
  }

  transformLinePlot_(yAxisScale, chart) {
    const pathGenerator = d3.line()
        .x(d => this.scaleForXAxis_(d.x))
        .y(d => yAxisScale(d.y))
        .curve(d3.curveMonotoneX);
    this.yAxisGenerator_.scale(yAxisScale);
    this.yAxisDrawing_.call(this.yAxisGenerator_);
    chart.selectAll('.line-dot')
        .attr('cx', datum => this.scaleForXAxis_(datum.x))
        .attr('cy', datum => yAxisScale(datum.y));
    chart.selectAll('.line-plot')
        .attr('d', pathGenerator);
  }

  setUpZoom_(zoom, chart, chartDimensions) {
    const onZoom = () => {
      const transform = d3.event.transform;
      const transformedScaleForYAxis = transform.rescaleY(this.scaleForYAxis_);
      this.transformLinePlot_(transformedScaleForYAxis, chart);
    };
    zoom.on('zoom', onZoom).scaleExtent([1, Infinity]);
    // The following invisible rectangle is there just to catch
    // mouse events for zooming. It's not possible to listen on
    // the chart itself because it is a g element (which does not
    // capture mouse events).
    chart.append('rect')
        .attr('width', chartDimensions.width)
        .attr('height', chartDimensions.height)
        .attr('class', 'zoom-listener')
        .style('opacity', 0)
        .call(zoom);
  }

  setUpZoomReset_(zoom, chart, chartDimensions) {
    // Gives some padding between the x-axis and the reset button.
    const padding = 10;
    const resetButton = chart.append('svg')
        .attr('width', '10em')
        .attr('height', '2em')
        .attr('x', `${chartDimensions.width + padding}px`)
        .attr('y', `${chartDimensions.height}px`)
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
          chart.select('.zoom-listener')
              .call(zoom.transform, d3.zoomIdentity);
          this.transformLinePlot_(this.scaleForYAxis_, chart);
        });
  }
}
