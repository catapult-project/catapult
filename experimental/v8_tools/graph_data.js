'use strict';
/**
 * Represents the data to be displayed on a graph and enables processing
 * of the data for display. This class is to be used as input to a
 * graph plotter.
 */
class GraphData {
  constructor() {
    /** @private @const {xAxis: string, yAxis:string} */
    this.labels = {
      xAxis: '',
      yAxis: '',
      title: '',
    };
    /** @private @const {Array<Object>} */
    this.dataSources = [];
    /** @private @const {Object} */
    this.plotter_ = new GraphPlotter(this);
  }

  /**
   * Sets the label for the x-axis if provided as an argument and returns
   * this instance for method chaining. If no label is provided then
   * the current label is returned.
   * @param {string} label
   * @return {(string|GraphData)}
   */
  xAxis(label) {
    if (arguments.length > 0) {
      this.labels.xAxis = label;
      return this;
    }
    return this.labels.xAxis;
  }

  /**
   * Sets the label for the y-axis if provided as an argument and returns
   * this instance for method chaining. If no label is provided then
   * the current label is returned.
   * @param {string} label
   * @return {(string|GraphData)}
   */
  yAxis(label) {
    if (arguments.length > 0) {
      this.labels.yAxis = label;
      return this;
    }
    return this.labels.yAxis;
  }

  /**
   * Sets the label for the title if provided as an argument and returns
   * this instance for method chaining. If no label is provided then
   * the current label is returned.
   * @param {string} label
   * @return {(string|GraphData)}
   */
  title(label) {
    if (arguments.length > 0) {
      this.labels.title = label;
      return this;
    }
    return this.labels.title;
  }

  /**
   * Registers the supplied data as a dataSource, enabling it to be plotted and
   * processed. The data source can supply various attributes: the color is
   * optional and defines the line color to be used (useful for when multiple
   * data sources are being plotted), the data attribute is the supply of raw
   * data to be processed and the key attribute is the label which will be
   * assigned to the data on the legend.
   * @param {{data: Array<Object>, color: string, key: string}} dataSource
   * @return {GraphData}
   */
  addData(dataSource) {
    const { data, color, key } = dataSource;
    if (!(data instanceof Array)) {
      throw new Error(
          'The data attribute of the supplied dataSource must be an Array');
    }
    this.dataSources.push({
      data,
      color: color ? color : 'black',
      key: key ? key : `Line ${this.dataSources.length}`,
    });
    return this;
  }

  /**
   * Returns the maximum value from all dataSources based on the value
   * computed by projection.
   * @param {function(Object): number} projection
   * @return {number}
   */
  max_(projection) {
    const projectAll = dataSource => dataSource.data.map(projection);
    const maxReducer =
      (acc, curr) => Math.max(acc, Math.max(...projectAll(curr)));
    return this.dataSources.reduce(maxReducer, Number.MIN_VALUE);
  }

  /**
   * Finds the maximum value along the points for the x-axis.
   * This is useful when computing appropriate scales for the x-axis.
   * @return {number}
   */
  xAxisMax() {
    return this.max_(point => point.x);
  }

  /**
   * Finds the maximum value along the points for the y-axis.
   * This is useful when computing appropriate scales for the y-axis.
   * @return {number}
   */
  yAxisMax() {
    return this.max_(point => point.y);
  }

  /**
   * Applies the supplied processingFn to all of the dataSources held
   * in this instance and replaces the old data with the newly processed data.
   * The processing function supplied to process should return data in
   * a format suitable for plotting (e.g., an array of
   * objects, consisting of x and y co-ordinates, for a line plot).
   * @param {function(Array<?>): Array<Object>} processingFn
   * @returns {GraphData}
   */
  process(processingFn) {
    if (typeof processingFn !== 'function') {
      const type = typeof processingFn;
      throw new TypeError(
          `Expected argument of type function, but got: ${type}`);
    }
    this.dataSources.forEach(
        source => source.data = processingFn(source.data));
    return this;
  }

  /**
   * Computes the cumulative frequency for all data sources provided
   * and plots the results to the screen. The provided
   * data field in the dataSource must be a list of numbers.
   */
  plotCumulativeFrequency() {
    this.process(GraphData.computeCumulativeFrequencies);
    this.plotter_.linePlot();
  }

  /**
   * Computes the cumulative frequency for the list of values provided.
   * @param {Array<number>} data
   * @returns {Array<Object>}
   */
  static computeCumulativeFrequencies(data) {
    const sortedData = data.sort((a, b) => a - b);
    return sortedData.map((value, i) => {
      return {
        x: i,
        y: value,
      };
    });
  }
}
