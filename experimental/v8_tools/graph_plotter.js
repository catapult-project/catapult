'use strict';
/**
 * This class provides the common functionality required for displaying graphs.
 * In particular, it performs the set up of the svg in preparation
 * for plotting charts. Concrete plotting strategies can be
 * provided to the plot method to perform plotting of different charts.
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
    /** @private {number} */
    this.canvasHeight_ = 720;
    /** @private {number} */
    this.canvasWidth_ = 1280;
    /* Provides spacing around the chart for labels and the axes. */
    const margins = {
      top: 50,
      right: 200,
      left: 80,
      bottom: 50,
    };
    const width = this.canvasWidth_ - margins.left - margins.right;
    const height = this.canvasHeight_ - margins.top - margins.bottom;
    /** @private @const {Object} chartDimensions
     * Provides access to the chart's dimensions to aid plotters
     * (e.g., for when computing scales for the axes).
     */
    this.chartDimensions = {
      margins,
      width,
      height,
    };
    /** @private @const {Object} */
    this.background_ = d3.select('#canvas').append('svg:svg')
        .attr('width', this.canvasWidth_)
        .attr('height', this.canvasHeight_);
    /** @private @const {Object} */
    this.chart_ = this.background_.append('g')
        .attr('transform', `translate(${this.chartDimensions.margins.left}, 
                  ${this.chartDimensions.margins.top})`);
    /* Appending a clip path rectangle prevents any drawings with the
     * clip-path: url(#plot-clip) attribute from being displayed outside
     * of the chart area.
     */
    this.chart_.append('defs')
        .append('clipPath')
        .attr('id', 'plot-clip')
        .append('rect')
        .attr('width', this.chartDimensions.width)
        .attr('height', this.chartDimensions.height);
    /** @private {Object} */
    this.legend_ = this.createLegend_();
  }

  createLegend_() {
    const padding = 5;
    return this.chart_.append('g')
        .attr('class', 'legend')
        .attr('transform',
            `translate(${this.chartDimensions.width + padding},
                ${this.chartDimensions.margins.top})`);
  }

  labelTitle_() {
    this.chart_.append('text')
        .attr('x', this.chartDimensions.width / 2)
        .attr('y', 0 - this.chartDimensions.margins.top / 2)
        .attr('text-anchor', 'middle')
        .text(this.graph_.title());
  }

  labelAxis_() {
    const chartBottom =
      this.chartDimensions.height + this.chartDimensions.margins.bottom;
    this.chart_.append('text')
        .attr('transform', `translate(${this.chartDimensions.width / 2}, 
            ${chartBottom})`)
        .attr('text-anchor', 'middle')
        .text(this.graph_.xAxis());

    this.chart_.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - (this.chartDimensions.margins.left / 2))
        .attr('x', 0 - (this.chartDimensions.height / 2))
        .attr('text-anchor', 'middle')
        .text(this.graph_.yAxis());
  }

  /**
   * Removes the graph from the UI by deleting the SVG associated with it.
   * This should be called before creating and displaying a new GraphPlotter.
   */
  remove() {
    this.background_.remove();
  }

  /**
   * Draws a plot by calling the plot method of the supplied plotter.
   * @param {Plotter} plotter
   * Strategy for plotting data to the chart. It is the responsibility of this
   * class to render the axes, the plot itself and any legend information.
   */
  plot(plotter) {
    this.labelTitle_();
    this.labelAxis_();
    /* Other classes should not be able to change chartDimensions
    * as then it will no longer reflect the chart's
    * true dimensions.
    */
    const dimensionsCopy = Object.assign({}, this.chartDimensions);
    plotter.plot(this.graph_, this.chart_, this.legend_, dimensionsCopy);
  }
}
