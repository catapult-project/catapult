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
    };
    /** @private @const {Array<Object>} */
    this.dataSources = [];
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
   * Registers the supplied data as a dataSource, enabling it to be plotted and
   * processed.
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
   * The processing function supplied to process should accept an array of
   * objects (consisting of x,y co-ordinates) and return an array of objects
   * in the same format.
   * @param {function(Array<Object>): Array<Object>} processingFn
   * @returns {GraphData}
   */
  process(processingFn) {
    this.dataSources.forEach(
        source => source.data = processingFn(source.data));
    return this;
  }

  /**
   * Sorts the list of x, y points according to their y value and
   * replaces the x values with the new sorted position of each point.
   * @param {Array<Object>} data
   * @returns {Array<Object>}
   */
  static sortYValues(data) {
    const sortedData = data.sort(
        (pointOne, pointTwo) => pointOne.y - pointTwo.y);
    sortedData.forEach((datum, i) => datum.x = i);
    return sortedData;
  }
}
