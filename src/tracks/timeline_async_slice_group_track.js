// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracks.timeline_slice_group_track');
base.require('ui');
base.exportTo('tracks', function() {

  /**
   * A track that displays a TimelineAsyncSliceGroup.
   * @constructor
   * @extends {TimelineSliceGroup}
   */

  var TimelineAsyncSliceGroupTrack = base.ui.define(
      tracks.TimelineSliceGroupTrack);

  TimelineAsyncSliceGroupTrack.prototype = {

    __proto__: tracks.TimelineSliceGroupTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-async-slice-group-track');
    },

    addSliceTrack_: function(slices) {
      var track = tracks.TimelineSliceGroupTrack.prototype.addSliceTrack_.call(
          this, slices);
      track.asyncStyle = true;
      return track;
    },

    /**
     * Breaks up the list of slices into N rows, each of which is a list of
     * slices that are non overlapping.
     *
     * It uses a very simple approach: walk through the slices in sorted order
     * by start time. For each slice, try to fit it in an existing subRow. If it
     * doesn't fit in any subrow, make another subRow.
     */
    buildSubRows_: function() {
      var slices = tracing.filterSliceArray(this.categoryFilter,
                                            this.group_.slices);
      slices.sort(function(x, y) {
        return x.start - y.start;
      });

      var subRows = [];
      for (var i = 0; i < slices.length; i++) {
        var slice = slices[i];

        var found = false;
        for (var j = 0; j < subRows.length; j++) {
          var subRow = subRows[j];
          var lastSliceInSubRow = subRow[subRow.length - 1];
          if (slice.start >= lastSliceInSubRow.end) {
            found = true;
            // Instead of plotting one big slice for the entire
            // TimelineAsyncEvent, we plot each of the subSlices.
            if (slice.subSlices === undefined || slice.subSlices.length < 1)
              throw new Error('TimelineAsyncEvent missing subSlices: ') +
                  slice.name;
            for (var k = 0; k < slice.subSlices.length; k++)
              subRow.push(slice.subSlices[k]);
            break;
          }
        }
        if (!found) {
          var subRow = [];
          if (slice.subSlices !== undefined) {
            for (var k = 0; k < slice.subSlices.length; k++)
              subRow.push(slice.subSlices[k]);
            subRows.push(subRow);
          }
        }
      }
      return subRows;
    }
  };

  return {
    TimelineAsyncSliceGroupTrack: TimelineAsyncSliceGroupTrack
  };
});
