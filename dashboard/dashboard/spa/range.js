/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class Range {
  constructor() {
    this.min_ = undefined;
    this.max_ = undefined;
  }

  clone() {
    if (this.isEmpty) return new Range();
    return Range.fromExplicitRange(this.min_, this.max_);
  }

  get isEmpty() {
    return ((this.min_ === undefined) || (this.min_ === null) ||
            (this.max_ === undefined) || (this.max_ === null));
  }

  addValue(value) {
    if (this.isEmpty) {
      this.max_ = value;
      this.min_ = value;
      return;
    }
    this.max_ = Math.max(this.max_, value);
    this.min_ = Math.min(this.min_, value);
  }

  addRange(range) {
    if (range.isEmpty) return;
    this.addValue(range.min);
    this.addValue(range.max);
  }

  set min(min) {
    this.min_ = min;
  }

  get min() {
    if (this.isEmpty) return undefined;
    return this.min_;
  }

  get max() {
    if (this.isEmpty) return undefined;
    return this.max_;
  }

  set max(max) {
    this.max_ = max;
  }

  get duration() {
    if (this.isEmpty) return 0;
    return this.max_ - this.min_;
  }

  containsExplicitRangeInclusive(min, max) {
    if (this.isEmpty) return false;
    return this.min_ <= min && max <= this.max_;
  }

  intersectsExplicitRangeInclusive(min, max) {
    if (this.isEmpty) return false;
    return this.min_ <= max && min <= this.max_;
  }

  containsRangeInclusive(range) {
    if (range.isEmpty) return false;
    return this.containsExplicitRangeInclusive(range.min_, range.max_);
  }

  intersectsRangeInclusive(range) {
    if (range.isEmpty) return false;
    return this.intersectsExplicitRangeInclusive(range.min_, range.max_);
  }

  findIntersection(range) {
    if (this.isEmpty || range.isEmpty) return new Range();

    const min = Math.max(this.min, range.min);
    const max = Math.min(this.max, range.max);

    if (max < min) return new Range();

    return Range.fromExplicitRange(min, max);
  }

  toJSON() {
    if (this.isEmpty) return {isEmpty: true};
    return {
      isEmpty: false,
      max: this.max,
      min: this.min
    };
  }

  /**
  * Merges the current Range into an array of disconnected Ranges which has
  * been sorted by min.
  *
  *  array: |=====|    |==========|
  *   self:         |===|
  * result: |=====| |=============|
  *
  *
  *  array: |=====|       |=======|
  *   self:         |===|
  * result: |=====| |===| |=======|
  *
  *
  *  array: |=====|       |=======|
  *   self:   |==|
  * result: |=====|       |=======|
  *
  *
  *  array: |=====|       |=======|
  *   self: |========|
  * result: |========|    |=======|
  *
  * @param {Array.<Range>} sortedArray
  * @returns {Array.<Range>} An array of ranges that is the result
  * of the merge.
  */
  mergeIntoArray(sortedArray) {
    if (this.isEmpty) {
      // Self is an empty range, so just return a clone of the array.
      return sortedArray
          .filter(range => !range.isEmpty)
          .map(range => range.clone());
    }

    let hasInsertedSelf = false;
    const result = [];
    const selfClone = this.clone();

    for (const range of sortedArray) {
      // Filter out empty ranges.
      if (range.isEmpty) continue;

      if (range.containsRangeInclusive(selfClone)) {
        // This range already contains selfClone; do not insert selfClone.
        hasInsertedSelf = true;
        result.push(range.clone());
      } else if (selfClone.containsRangeInclusive(range)) {
        // selfClone already contains this range; ignore it.
      } else if (range.intersectsRangeInclusive(selfClone)) {
        // selfClone shares some with this range; merge it into selfClone.
        selfClone.addRange(range);
      } else {
        if (!hasInsertedSelf && range.min > selfClone.max) {
          // This range is past selfClone; let's insert before we forget.
          result.push(selfClone);
          hasInsertedSelf = true;
        }

        result.push(range.clone());
      }
    }

    if (!hasInsertedSelf) {
      result.push(selfClone);
    }

    return result;
  }

  static fromDict(d) {
    if (d.isEmpty === true) return new Range();
    if (d.isEmpty === false) {
      const range = new Range();
      range.min = d.min;
      range.max = d.max;
      return range;
    }
    throw new Error('Not a range');
  }

  static fromExplicitRange(min, max) {
    const range = new Range();
    range.min = min;
    range.max = max;
    return range;
  }

  /**
  * Subtracts the intersection of |rangeA| and |rangeB| from |rangeA| and
  * returns the remaining ranges as return. |rangeA| and |rangeB| are
  * not changed during the subtraction.
  *
  * rangeA:       |==========|
  * rangeB:          |===|
  * result:       |==|   |===|
  *
  * @param {Range} rangeA
  * @param {Range} rangeB
  * @return {Array.<Range>} An array of ranges which is the result of
  * the subtraction.
  */
  static findDifference(rangeA, rangeB) {
    if (!rangeA || rangeA.duration < 0 || !rangeB || rangeB.duration < 0) {
      throw new Error(`Couldn't subtract ranges`);
    }
    const resultRanges = [];

    if (rangeA.isEmpty) return resultRanges;
    if (rangeB.isEmpty) return [rangeA.clone()];

    const intersection = rangeA.findIntersection(rangeB);
    if (intersection.isEmpty) {
      return [rangeA.clone()];
    }
    if (rangeA.duration === 0 && rangeB.duration === 0) {
      if (intersection.empty) return [rangeA.clone()];
      else if (intersection.duration === 0) return resultRanges;
      throw new Error(`Two points' intersection can only be a point or empty`);
    }

    //  rangeA:       |==========|
    //  rangeB:          |===|
    //  result:       |==|   |===|
    const leftRange = Range.fromExplicitRange(
        rangeA.min, intersection.min);
    if (leftRange.duration > 0) {
      resultRanges.push(leftRange);
    }
    const rightRange = Range.fromExplicitRange(
        intersection.max, rangeA.max);
    if (rightRange.duration > 0) {
      resultRanges.push(rightRange);
    }
    return resultRanges;
  }
}
