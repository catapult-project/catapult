'use strict';
/**
 * Concrete implementation of Plotter strategy for creating
 * bar charts.
 * @implements {Plotter}
 */
class BarPlotter {
  constructor() {
    /** @private @const {number} x_
     * The x axis column in the graph data table.
     */
    this.x_ = 0;
    /** @private @const {number} x_
     * The y axis column in the graph data table.
     */
    this.y_ = 1;
  }
  /**
   * Initalises the chart by computing the scales for the axes and
   * drawing them. It also applies the labels to the graph (axes and
   * graph titles).
   * @param {GraphData} graph Data to be drawn.
   * @param {Object} chart Chart to draw to.
   * @param {Object} chartDimensions Size of the chart.
   */
  initChart_(graph, chart, chartDimensions) {
    this.outerBandScale_ = this.createXAxisScale_(graph, chartDimensions);
    this.scaleForYAxis_ = this.createYAxisScale_(graph, chartDimensions);
    this.xAxisGenerator_ = d3.axisBottom(this.outerBandScale_);
    this.yAxisGenerator_ = d3.axisLeft(this.scaleForYAxis_);
    chart.append('g')
        .call(this.xAxisGenerator_)
        .attr('class', 'xaxis')
        .attr('transform', `translate(0, ${chartDimensions.height})`);
    this.yAxisDrawing_ = chart.append('g')
        .call(this.yAxisGenerator_);
    // Each story is assigned a band by the createXAxisScale function
    // which maintains the positions in which each category of the chart
    // will be rendered. This further divides these bands into
    // sub-bands for each data source, so that different labels can be
    // grouped within the same category.
    this.innerBandScale_ = this.createInnerBandScale_(graph);
  }

  getBarCategories_(graph) {
    // Process data sources so that their data contains only their categories.
    const dataSources = graph.process(data => data.map(row => row[this.x_]));
    if (dataSources.length > 0) {
      return dataSources[0].data;
    }
    return [];
  }

  createXAxisScale_(graph, chartDimensions) {
    return d3.scaleBand()
        .domain(this.getBarCategories_(graph))
        .range([0, chartDimensions.width])
        .padding(0.2);
  }

  createYAxisScale_(graph, chartDimensions) {
    return d3.scaleLinear()
        .domain([graph.max(row => this.computeAverage_(row[this.y_])), 0])
        .range([0, chartDimensions.height]);
  }

  createInnerBandScale_(graph) {
    const keys = graph.keys();
    return d3.scaleBand()
        .domain(keys)
        .range([0, this.outerBandScale_.bandwidth()]);
  }

  /**
   * Attempts to compute the average of the given numbers but returns
   * 0 if the supplied array is empty.
   * @param {Array<number>} data
   * @returns {number}
   */
  computeAverage_(data) {
    if (!data.every(val => typeof val === 'number')) {
      throw new TypeError('Expected an array of numbers.');
    }
    return data.reduce((a, b) => a + b, 0) / data.length || 0;
  }
  /**
   * Draws a bar chart to the canvas. If there are multiple dataSources it will
   * plot them both and label their colors in the legend. This expects the data
   * in graph to be formatted as a table, with the first column being categories
   * and the second being the corresponding values.
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
    const computeAllAverages = stories =>
      stories.map(
          ([story, rawData]) => [story, this.computeAverage_(rawData)]);
    const dataInAverages = graph.process(computeAllAverages);
    const getClassNameSuffix = GraphUtils.getClassNameSuffixFactory();
    dataInAverages.forEach(({ data, color, key }, index) => {
      const barStart = category =>
        this.outerBandScale_(category) + this.innerBandScale_(key);
      const barWidth = this.innerBandScale_.bandwidth();
      const barHeight = value =>
        chartDimensions.height - this.scaleForYAxis_(value);
      chart.selectAll(`.bar-${getClassNameSuffix(key)}`)
          .data(data)
          .enter()
          .append('rect')
          .attr('class', `.bar-${getClassNameSuffix(key)}`)
          .attr('x', d => barStart(d[this.x_]))
          .attr('y', d => this.scaleForYAxis_(d[this.y_]))
          .attr('width', barWidth)
          .attr('height', d => barHeight(d[this.y_]))
          .attr('fill', color)
          .on('click', d =>
            graph.interactiveCallbackForBarPlot(d[this.x_], key));
      const boxSize = 10;
      const offset = `${index}em`;
      legend.append('rect')
          .attr('fill', color)
          .attr('height', boxSize)
          .attr('width', boxSize)
          .attr('y', offset)
          .attr('x', 0);
      legend.append('text')
          .text(key)
          .attr('x', boxSize)
          .attr('y', offset)
          .attr('dy', boxSize)
          .attr('text-anchor', 'start');
    });
    const tickRotation = -30;
    d3.selectAll('.xaxis .tick text')
        .attr('text-anchor', 'end')
        .attr('font-size', 12)
        .attr('transform', `rotate(${tickRotation})`)
        .append('title')
        .text(text => text);
  }
}
