// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


/**
 * @fileoverview Helper functions for doing intersections and iteration
 * over sorted arrays and intervals.
 *
 */
cr.define('tracing', function() {
  /**
   * Finds the first index in the array whose value is >= loVal.
   *
   * The key for the search is defined by the mapFn. This array must
   * be prearranged such that ary.map(mapFn) would also be sorted in
   * ascending order.
   *
   * @param {Array} ary An array of arbitrary objects.
   * @param {function():*} mapFn Callback that produces a key value
   *     from an element in ary.
   * @param {number} loVal Value for which to search.
   * @return {Number} Offset o into ary where all ary[i] for i <= o
   *     are < loVal, or ary.length if loVal is greater than all elements in
   *     the array.
   */
  function findLowIndexInSortedArray(ary, mapFn, loVal) {
    if (ary.length == 0)
      return 1;

    var low = 0;
    var high = ary.length - 1;
    var i, comparison;
    var hitPos = -1;
    while (low <= high) {
      i = Math.floor((low + high) / 2);
      comparison = mapFn(ary[i]) - loVal;
      if (comparison < 0) {
        low = i + 1; continue;
      } else if (comparison > 0) {
        high = i - 1; continue;
      } else {
        hitPos = i;
        high = i - 1;
      }
    }
    // return where we hit, or failing that the low pos
    return hitPos != -1 ? hitPos : low;
  }

  /**
   * Finds an index in an array of intervals that either
   * intersects the provided loVal, or if no intersection is found,
   * the index of the first interval whose start is > loVal.
   *
   * The array of intervals is defined implicitly via two mapping functions
   * over the provided ary. mapLoFn determines the lower value of the interval,
   * mapWidthFn the width. Intersection is lower-inclusive, e.g. [lo,lo+w).
   *
   * The array of intervals formed by this mapping must be non-overlapping and
   * sorted in ascending order by loVal.
   *
   * @param {Array} ary An array of objects that can be converted into sorted
   *     nonoverlapping ranges [x,y) using the mapLoFn and mapWidth.
   * @param {function():*} mapLoFn Callback that produces the low value for the
   *     interval represented by an  element in the array.
   * @param {function():*} mapLoFn Callback that produces the width for the
   *     interval represented by an  element in the array.
   * @param {number} loVal The low value for the search.
   * @return {Number} An index in the array that intersects or is first-above
   *     loVal, -1 if none found and loVal is below than all the intervals,
   *     ary.length if loVal is greater than all the intervals.
   */
  function findLowIndexInSortedIntervals(ary, mapLoFn, mapWidthFn, loVal) {
    var first = findLowIndexInSortedArray(ary, mapLoFn, loVal);
    if (first == 0) {
      if (loVal >= mapLoFn(ary[0]) &&
          loVal < mapLoFn(ary[0] + mapWidthFn(ary[0]))) {
        return 0;
      } else {
        return -1;
      }
    } else if (first <= ary.length &&
               loVal >= mapLoFn(ary[first - 1]) &&
               loVal < mapLoFn(ary[first - 1]) + mapWidthFn(ary[first - 1])) {
      return first - 1;
    } else {
      return ary.length;
    }
  }

  /**
   * Calls cb for all intervals in the implicit array of intervals
   * defnied by ary, mapLoFn and mapHiFn that intersect the range
   * [loVal,hiVal)
   *
   * This function uses the same scheme as findLowIndexInSortedArray
   * to define the intervals. The same restrictions on sortedness and
   * non-overlappingness apply.
   *
   * @param {Array} ary An array of objects that can be converted into sorted
   * nonoverlapping ranges [x,y) using the mapLoFn and mapWidth.
   * @param {function():*} mapLoFn Callback that produces the low value for the
   * interval represented by an element in the array.
   * @param {function():*} mapLoFn Callback that produces the width for the
   * interval represented by an element in the array.
   * @param {number} The low value for the search, inclusive.
   * @param {number} loVal The high value for the search, non inclusive.
   * @param {function():*} cb The function to run for intersecting intervals.
   */
  function iterateOverIntersectingIntervals(ary, mapLoFn, mapWidthFn, loVal,
                                            hiVal, cb) {
    if (loVal > hiVal) return;

    var i = findLowIndexInSortedArray(ary, mapLoFn, loVal);
    if (i == -1) {
      return;
    }
    if (i > 0) {
      var hi = mapLoFn(ary[i - 1]) + mapWidthFn(ary[i - 1]);
      if (hi >= loVal) {
        cb(ary[i - 1]);
      }
    }
    if (i == ary.length) {
      return;
    }

    for (var n = ary.length; i < n; i++) {
      var lo = mapLoFn(ary[i]);
      if (lo >= hiVal)
        break;
      cb(ary[i]);
    }
  }

  /**
   * Non iterative version of iterateOverIntersectingIntervals.
   *
   * @return {Array} Array of elements in ary that intersect loVal, hiVal.
   */
  function getIntersectingIntervals(ary, mapLoFn, mapWidthFn, loVal, hiVal) {
    var tmp = [];
    iterateOverIntersectingIntervals(ary, mapLoFn, mapWidthFn, loVal, hiVal,
                                     function(d) {
                                       tmp.push(d);
                                     });
    return tmp;
  }

  return {
    findLowIndexInSortedArray: findLowIndexInSortedArray,
    findLowIndexInSortedIntervals: findLowIndexInSortedIntervals,
    iterateOverIntersectingIntervals: iterateOverIntersectingIntervals,
    getIntersectingIntervals: getIntersectingIntervals
  };
});
