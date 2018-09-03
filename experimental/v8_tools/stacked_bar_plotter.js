'use strict';
/**
 * Concrete implementation of Plotter strategy for creating
 * stacked bar charts.
 * @implements {Plotter}
 */
class StackedBarPlotter {
  constructor() {
    /** @private @const {number} name_
     * The column in a datasource data referring to the
     * name of the associated data.
     */
    this.name_ = 0;
    /** @private @const {number} data_
     * The column in a datasource referring to the data.
     */
    this.data_ = 1;
  }
  /**
   * Initalises the chart by computing the scales for the axes and
   * drawing them. It also applies the labels to the graph (axes and
   * graph titles).
   * @param {GraphData} graph GraphData instance containing the raw data.
   * @param {Object} chart Chart to draw to.
   * @param {Object} chartDimensions Size of the chart.
   * @param {Object} data The processed data.
   */
  initChart_(graph, chart, chartDimensions, data) {
    this.outerBandScale_ = this.createXAxisScale_(graph, chartDimensions);
    this.scaleForYAxis_ = this.createYAxisScale_(chartDimensions, data);
    this.xAxisGenerator_ = d3.axisBottom(this.outerBandScale_);
    this.yAxisGenerator_ = d3.axisLeft(this.scaleForYAxis_);
    chart.append('g')
        .attr('class', 'xaxis')
        .call(this.xAxisGenerator_)
        .attr('transform', `translate(0, ${chartDimensions.height})`);
    this.yAxisDrawing_ = chart.append('g')
        .call(this.yAxisGenerator_);
    this.keys_ = graph.keys();
    // Each story is assigned a band by the createXAxisScale function
    // which maintains the positions in which each category of the chart
    // will be rendered. This further divides these bands into
    // sub-bands for each data source, so that different labels can be
    // grouped within the same category.
    this.innerBandScale_ = this.createInnerBandScale_(graph);
  }

  getBarCategories_(graph) {
    // Process data sources so that their data contains only their categories.
    const dataSources = graph.process(data => data.map(row => row[this.name_]));
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

  createYAxisScale_(chartDimensions, sources) {
    const getStackHeights =
        stackNames => stackNames.map(stack => stack[this.data_].height);
    const getBarHeight =
        story => this.sum_(getStackHeights(story[this.data_]));
    const maxHeight =
        bars => d3.max(bars.map(story => getBarHeight(story)));
    const maxHeightOfAllSources =
        d3.max(sources.map(({ data }) => maxHeight(data)));
    return d3.scaleLinear()
        .domain([maxHeightOfAllSources, 0]).nice()
        .range([0, chartDimensions.height]);
  }

  createInnerBandScale_() {
    return d3.scaleBand()
        .domain(this.keys_)
        .range([0, this.outerBandScale_.bandwidth()]);
  }

  /**
   * Attempts to compute the average of the given numbers but returns
   * 0 if the supplied array is empty.
   * @param {Array<number>} data
   * @returns {number}
   */
  avg_(data) {
    return this.sum_(data) / data.length || 0;
  }

  sum_(data) {
    if (!data.every(val => typeof val === 'number')) {
      throw new TypeError('Expected an array of numbers.');
    }
    return data.reduce((a, b) => a + b, 0);
  }

  /**
   * Computes the start position and height of each stack for
   * the bar corresponing to the supplied data.
   * @param {Object} data The data for a single bar. Each key
   * corresponds to the label for the stack and the value that
   * key represents the values associated with that label.
   * For example:
   * {
   *  stackOne: [numbers...]
   *  stackTwo: [numbers...]
   * }
   * will compute the positions for a bar that has two stacks,
   * the height of each being the average of numbers...
   */
  stackLocations_(data) {
    const stackedAverages = [];
    let cumulativeAvg = 0;
    for (const [name, values] of Object.entries(data)) {
      const average = this.avg_(values);
      const yValues = {
        start: cumulativeAvg,
        height: average,
      };
      cumulativeAvg += average;
      stackedAverages.push([name, yValues]);
    }
    return stackedAverages;
  }

  getNumericLabelForKey_(key) {
    return this.keys_.indexOf(key) + 1;
  }
  /**
   * Draws a stacked bar chart to the canvas. This expects the data
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
    const formatBars = bars =>
      bars.map(
          ([story, values]) => [story, this.stackLocations_(values)]);
    const bars = graph.process(formatBars);
    this.initChart_(graph, chart, chartDimensions, bars);
    bars.forEach(({ data, key }) => {
      data.forEach((bars) => {
        this.drawStackedBar_(chart, bars, chartDimensions, key);
      });
    });
    if (bars.length > 0) {
      const bar = bars[0];
      const stacks = bar.data;
      if (stacks.length > 0) {
        const stackNames = stacks[0][this.data_].map(([name]) => name);
        this.drawLegendLabels_(legend, stackNames);
      }
    }
  }

  drawLegendLabels_(legend, stackNames) {
    stackNames.forEach((stack, i) => {
      const boxSize = 10;
      const offset = `${i * 1}em`;
      legend.append('rect')
          .attr('fill', d3.schemeCategory10[i])
          .attr('height', boxSize)
          .attr('width', boxSize)
          .attr('y', offset)
          .attr('x', 0);
      legend.append('text')
          .text(stack)
          .attr('x', boxSize)
          .attr('y', offset)
          .attr('dy', boxSize)
          .attr('text-anchor', 'start');
    });
    this.keys_.forEach((key, i) => {
      const belowStackNames = `${stackNames.length + 1}em`;
      const offset = `${i}em`;
      legend.append('text')
          .text(`${this.getNumericLabelForKey_(key)}: ${key}`)
          .attr('y', belowStackNames)
          .attr('dy', offset)
          .append('title')
          .text(key);
    });
  }

  drawStackedBar_(selection, bars, chartDimensions, key) {
    const barName = bars[this.name_];
    const stacks = bars[this.data_];
    const colors = d3.schemeCategory10;
    const x = this.outerBandScale_(barName) + this.innerBandScale_(key);
    let totalHeight = 0;
    stacks.forEach((stack, i) => {
      const positions = stack[this.data_];
      const height =
          chartDimensions.height - this.scaleForYAxis_(positions.height);
      selection.append('rect')
          .attr('x', x)
          .attr('y', this.scaleForYAxis_(positions.height + positions.start))
          .attr('width', this.innerBandScale_.bandwidth())
          .attr('height', height)
          .attr('fill', colors[i]);
      totalHeight += positions.height;
    });
    const barMid = x + this.innerBandScale_.bandwidth() / 2;
    selection.append('text')
        .text(this.getNumericLabelForKey_(key))
        .attr('fill', 'black')
        .attr('y', this.scaleForYAxis_(totalHeight))
        .attr('x', barMid)
        .append('title')
        .text(key);
  }
}
