'use strict';
/**
 * Concrete implementation of Plotter strategy for creating
 * box plots.
 * @implements {Plotter}
 */
class DotPlotter {
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
    this.xAxisGenerator_ = d3.axisBottom(this.scaleForXAxis_);
    // Draw the x-axis.
    chart.append('g')
        .call(this.xAxisGenerator_)
        .attr('transform', `translate(0, ${chartDimensions.height})`);
  }

  createXAxisScale_(graph, chartDimensions) {
    return d3.scaleLinear()
        .domain([0, graph.max(x => x)])
        .range([0, chartDimensions.width]);
  }

  getDotDiameter_() {
    return this.radius_ * 2;
  }
  /**
   * Collects the data into groups so that dots which would otherwise overlap
   * are stacked on top of each other instead. This is a rough implementation
   * and allows occasional overlap in some cases, where
   * values in adjacent bins overlap. However, in this case the overlap is
   * bounded to very few elements.
   */
  computeDotStacking_(data) {
    const bins = {};
    // Each bin corresponds to the size of the diameter of a dot,
    // so any data points in the same bin will definitely overlap.
    // This assumes that the x axis starts at 0.
    const binSize = Math.ceil(
        this.scaleForXAxis_.invert(this.getDotDiameter_()));
    data.forEach(datum => {
      // The lower bound of the bin will be some multiple of binSize so find
      // the closest such multiple less than the datum.
      const lowerBound = Math.round(datum) - (Math.round(datum) % binSize);
      const binMid = lowerBound + binSize / 2;
      if (!bins[binMid]) {
        bins[binMid] = [];
      }
      bins[binMid].push(datum);
    });
    const newPositions = [];
    // Give each value an offset so that they do not overlap.
    Object.values(bins).forEach(bin => {
      const binSize = bin.length;
      let stackOffset = - Math.floor(binSize / 2);
      if (stackOffset === -0) {
        stackOffset = 0;
      }
      bin.forEach(datum => {
        newPositions.push({
          x: datum,
          y: stackOffset,
        });
        stackOffset++;
      });
    });
    return newPositions;
  }

  /**
   * Draws a dot plot to the canvas. If there are multiple dataSources it will
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
    const gaps = graph.dataSources.length + 1;
    const gapSize = chartDimensions.height / gaps;
    let linePosition = gapSize;
    this.radius_ = 4;
    graph.process(this.computeDotStacking_.bind(this));
    graph.dataSources.forEach(({ data, color, key }, index) => {
      chart.append('line')
          .attr('x1', 0)
          .attr('x2', chartDimensions.width)
          .attr('y1', linePosition)
          .attr('y2', linePosition)
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', 4)
          .attr('stroke', 'gray');
      const dotOffset = datum =>
        linePosition - datum.y * this.getDotDiameter_();
      chart.selectAll(`.dot-${key}`)
          .data(data)
          .enter()
          .append('circle')
          .attr('cx', datum => this.scaleForXAxis_(datum.x))
          .attr('cy', dotOffset)
          .attr('r', this.radius_)
          .attr('fill', color)
          .attr('class', `dot-${key}`)
          .attr('clip-path', 'url(#plot-clip)');
      legend.append('text')
          .text(key)
          .attr('y', index + 'em')
          .attr('fill', color);
      linePosition += gapSize;
    });
  }
}

