'use strict';
/**
 * Performs a test of significance on supplied metric data.
 */
class MetricSignificance {
  constructor() {
    /**  @private @const {Object} data_ The data to perform tests on. */
    this.data_ = {};
    /** @private @const {number} criticalPValue_
     * The default p value below which the null hypothesis will be rejected.
     */
    this.criticalPValue_ = 0.05;
  }
  /**
   * Adds the given values to an entry for the supplied metric and
   * label. Tests of significance will be performed against the supplied
   * labels for the given metric. Therefore, each metric should be supplied
   * two labels.
   * @param {string} metric
   * @param {string} label
   * @param {Array<number>} value
   */
  add(metric, label, value) {
    if (!this.data_[metric]) {
      this.data_[metric] = {};
    }
    if (!this.data_[metric][label]) {
      this.data_[metric][label] = [];
    }
    const values = this.data_[metric][label];
    this.data_[metric][label] = values.concat(value);
  }
  /**
   * Returns the metrics which have been identified as having statistically
   * significant changes along with the evidence supporting this (the p values
   * and U values).
   * @return {Array<Object>} Name and evidence of metrics with
   * statistically significant changes.
   */
  mostSignificant() {
    const significantChanges = [];
    Object.entries(this.data_).forEach(([metric, runs]) => {
      const runsData = Object.values(runs);
      const numLabels = runsData.length;
      if (numLabels !== 2) {
        throw new Error(
            `Expected metric to have only two labels, received ${numLabels}`);
      }
      const evidence = mannwhitneyu.test(...runsData);
      if (evidence.p < this.criticalPValue_) {
        significantChanges.push({
          metric,
          evidence,
        });
      }
    });
    return significantChanges;
  }
}
