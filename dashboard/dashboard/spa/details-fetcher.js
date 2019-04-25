/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ChartTimeseries from './chart-timeseries.js';
import {BatchIterator, enumerate} from './utils.js';
import {LEVEL_OF_DETAIL, TimeseriesRequest} from './timeseries-request.js';

// DetailsTable contains one table body per line in the main chart, and one
// column per revisionRange.
//
// Each line may be merged from data for multiple timeseries.
// For each timeseries in a line, we may only be looking at a few
// revisionRanges
//
// for each line in chart
//   for each source of data for a line
//     fetch the timeseries
//     for each brushed revision range
//       fetch the details
//
// Yields {
//   errors,
//   timeseriesesByLine: [
//     {
//       lineDescriptor,
//       timeseriesesByRange: [
//         {
//           range,
//           timeserieses: [
//             {revision, avg, count, ..., revisions, annotations},
//           ],
//         },
//       ],
//     },
//   ],
// }.
export class DetailsFetcher {
  constructor(lineDescriptors, minRevision, maxRevision, revisionRanges) {
    this.revisionRanges_ = revisionRanges;

    // These describe the timeseries that will be fetched.
    this.fetchDescriptorsByLine_ = [];
    for (const lineDescriptor of lineDescriptors) {
      const fetchDescriptors = ChartTimeseries.createFetchDescriptors(
          lineDescriptor, LEVEL_OF_DETAIL.XY);
      for (const fetchDescriptor of fetchDescriptors) {
        fetchDescriptor.minRevision = minRevision;
        fetchDescriptor.maxRevision = maxRevision;
      }
      this.fetchDescriptorsByLine_.push({lineDescriptor, fetchDescriptors});
    }

    // This collates results.
    this.timeseriesesByLine_ = new TimeseriesesByLine(
        this.fetchDescriptorsByLine_, revisionRanges);

    // This batches the stream of results to reduce unnecessary rendering.
    // This does not batch the results themselves, they need to be collated by
    // this.timeseriesesByLine_.
    this.batches_ = new BatchIterator([]);
  }

  async* [Symbol.asyncIterator]() {
    if (!this.revisionRanges_ || this.revisionRanges_.length === 0) return;

    for (const [lineIndex, {fetchDescriptors}] of enumerate(
        this.fetchDescriptorsByLine_)) {
      for (const [fetchIndex, fetchDescriptor] of enumerate(
          fetchDescriptors)) {
        this.batches_.add(this.fetchTimeseries_(
            lineIndex, fetchIndex, fetchDescriptor));
      }
    }

    for await (const {results, errors} of this.batches_) {
      const timeseriesesByLine = this.timeseriesesByLine_.populatedResults;
      yield {errors, timeseriesesByLine};
    }
  }

  // Start fetches for detail data for each brushed revision range.
  async fetchTimeseries_(lineIndex, fetchIndex, fetchDescriptor) {
    const rangeFinder = new RangeFinder(fetchDescriptor);
    for (const [rangeIndex, revisionRange] of enumerate(
        this.revisionRanges_)) {
      fetchDescriptor = {
        ...fetchDescriptor,
        levelOfDetail: LEVEL_OF_DETAIL.DETAILS,
        ...await rangeFinder.findRange(revisionRange),
      };
      this.batches_.add(this.fetchDetails_(
          lineIndex, rangeIndex, fetchIndex, fetchDescriptor));
    }
  }

  // Collate detail data in timeseriesesByLine_.
  async* fetchDetails_(lineIndex, rangeIndex, fetchIndex, fetchDescriptor) {
    const request = new TimeseriesRequest(fetchDescriptor);
    for await (const timeseries of request.reader()) {
      this.timeseriesesByLine_.receive(
          lineIndex, rangeIndex, fetchIndex, timeseries);
      yield {/* Pump BatchIterator. */};
    }
  }
}

// This is a 3-dimensional matrix of timeserieses. The dimensions are
// [line in the main chart, brushed revision range, fetchDescriptor]
class TimeseriesesByLine {
  constructor(fetchDescriptorsByLine, revisionRanges) {
    this.timeseriesesByLine_ = [];

    for (const {lineDescriptor, fetchDescriptors} of fetchDescriptorsByLine) {
      const timeseriesesByRange = new Array(revisionRanges.length);

      for (const [rangeIndex, range] of enumerate(revisionRanges)) {
        const timeserieses = new Array(fetchDescriptors.length);
        timeseriesesByRange[rangeIndex] = {range, timeserieses};
      }

      this.timeseriesesByLine_.push({lineDescriptor, timeseriesesByRange});
    }
  }

  // Store a timeseries in the 3D matrix.
  receive(lineIndex, rangeIndex, fetchIndex, timeseries) {
    this.timeseriesesByLine_[lineIndex].timeseriesesByRange[
        rangeIndex].timeserieses[fetchIndex] = timeseries;
  }

  // Filters empty arrays from timeseriesesByLine.
  get populatedResults() {
    const result = [];
    for (const {lineDescriptor, timeseriesesByRange} of
      this.timeseriesesByLine_) {
      const filteredTimeseriesesByRange = [];

      for (const {range, timeserieses} of timeseriesesByRange) {
        const filteredTimeserieses = timeserieses.filter(ts => ts);
        if (filteredTimeserieses.length === 0) continue;

        filteredTimeseriesesByRange.push({
          range,
          timeserieses: filteredTimeserieses,
        });
      }

      if (filteredTimeseriesesByRange.length === 0) continue;

      result.push({
        lineDescriptor,
        timeseriesesByRange: filteredTimeseriesesByRange,
      });
    }
    return result;
  }
}

// Fetches XY data for a timeseries in order to find the precise revision
// range that should be fetched in order to display data about an approximate
// revision range.
export class RangeFinder {
  constructor(fetchDescriptor) {
    this.xyPromise_ = this.fetchXYTimeseries_(fetchDescriptor);
  }

  // Return {minRevision, maxRevision} to fetch in order to get the data
  // points within revisionRange (or the previous available point if that's
  // empty) plus one data point before revisionRange as a reference.
  async findRange(range) {
    const timeseries = await this.xyPromise_;
    return RangeFinder.matchRange(range, timeseries);
  }

  static matchRange(range, timeseries) {
    let maxIndex = Math.min(
        timeseries.length - 1,
        tr.b.findLowIndexInSortedArray(
            timeseries, d => d.revision, range.max));
    // Now, timeseries[maxIndex].revision >= range.max

    if (maxIndex > 0) {
      // Get the data point *before* range.max, not after it.
      maxIndex -= 1;
    }

    let minIndex = Math.min(
        timeseries.length,
        tr.b.findLowIndexInSortedArray(
            timeseries, d => d.revision, range.min));
    // Now, timeseries[minIndex].revision >= range.min

    while (minIndex > 0 && maxIndex < minIndex) {
      // Prevent minRevision > maxRevision.
      minIndex -= 1;
    }

    // Get the reference data point.
    if (minIndex > 0) minIndex -= 1;

    const minRevision = timeseries[minIndex].revision;
    const maxRevision = timeseries[maxIndex].revision;
    return {minRevision, maxRevision};
  }

  async fetchXYTimeseries_(fetchDescriptor) {
    const request = new TimeseriesRequest(fetchDescriptor);
    let timeseries;
    for await (timeseries of request.reader()) {
      // The service worker streams data as it receives it.
      // Wait for final data.
    }
    return timeseries;
  }
}
