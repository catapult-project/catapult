// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracks.timeline_container_track');
base.require('sorted_array_utils');
base.require('ui');

base.exportTo('tracks', function() {

  /**
   * A track that displays a TimelineSliceGroup.
   * @constructor
   * @extends {TimelineContainerTrack}
   */

  var TimelineSliceGroupTrack = base.ui.define(tracks.TimelineContainerTrack);

  TimelineSliceGroupTrack.prototype = {

    __proto__: tracks.TimelineContainerTrack.prototype,

    decorate: function() {
      this.classList.add('timeline-slice-group-track');
    },

    get group() {
      return this.group_;
    },

    set group(g) {
      this.group_ = g;
      this.updateChildTracks_();
    },

    set heading(h) {
      if (this.tracks_.length)
        this.tracks_[0].heading = h;
    },

    set tooltip(t) {
      if (this.tracks_.length)
        this.tracks_[0].tooltip = t;
    },

    set decorateHit(f) {
      this.decorateHit_ = f;
      this.updateChildTracks_();
    },

    applyCategoryFilter_: function() {
      this.updateChildTracks_();
    },

    addSliceTrack_: function(slices) {
      var track = new tracks.TimelineSliceTrack();
      track.slices = slices;
      track.decorateHit = this.decorateHit_;
      this.addTrack_(track);
      return track;
    },

    updateChildTracks_: function() {
      if (!this.group_) {
        this.visible = false;
        return;
      }

      var slices = tracing.filterSliceArray(this.categoryFilter,
                                            this.group_.slices);
      if (!slices.length) {
        this.visible = false;
        return;
      }
      this.visible = true;

      if (this.areArrayContentsSame_(this.filteredSlices_, slices))
        return;

      this.filteredSlices_ = slices;
      this.detach();
      this.subRows_ = this.buildSubRows_(slices);
      for (var srI = 0; srI < this.subRows_.length; srI++) {
        if (this.subRows_[srI].length) {
          this.addSliceTrack_(this.subRows_[srI]);
        }
      }
    },

    /**
     * Breaks up the list of slices into N rows, each of which is a list of
     * slices that are non overlapping.
     */
    buildSubRows_: function(slices) {
      // This function works by walking through slices by start time.
      //
      // The basic idea here is to insert each slice as deep into the subrow
      // list as it can go such that every subSlice is fully contained by its
      // parent slice.
      //
      // Visually, if we start with this:
      //  0:  [    a       ]
      //  1:    [  b  ]
      //  2:    [c][d]
      //
      // To place this slice:
      //               [e]
      // We first check row 2's last item, [d]. [e] wont fit into [d] (they dont
      // even intersect). So we go to row 1. That gives us [b], and [d] wont fit
      // into that either. So, we go to row 0 and its last slice, [a]. That can
      // completely contain [e], so that means we should add [e] as a subchild
      // of [a]. That puts it on row 1, yielding:
      //  0:  [    a       ]
      //  1:    [  b  ][e]
      //  2:    [c][d]
      //
      // If we then get this slice:
      //                      [f]
      // We do the same deepest-to-shallowest walk of the subrows trying to fit
      // it. This time, it doesn't fit in any open slice. So, we simply append
      // it to row 0:
      //  0:  [    a       ]  [f]
      //  1:    [  b  ][e]
      //  2:    [c][d]
      if (!slices.length)
        return [];

      var ops = [];
      for (var i = 0; i < slices.length; i++) {
        if (slices[i].subSlices)
          slices[i].subSlices.splice(0,
                                     slices[i].subSlices.length);
        ops.push(i);
      }

      ops.sort(function(ix, iy) {
        var x = slices[ix];
        var y = slices[iy];
        if (x.start != y.start)
          return x.start - y.start;

        // Elements get inserted into the slices array in order of when the
        // slices end.  Because slices must be properly nested, we break
        // start-time ties by assuming that the elements appearing earlier in
        // the slices array (and thus ending earlier) start later.
        return iy - ix;
      });

      var subRows = [[]];
      this.badSlices_ = [];  // TODO(simonjam): Connect this again.

      for (var i = 0; i < ops.length; i++) {
        var op = ops[i];
        var slice = slices[op];

        // Try to fit the slice into the existing subrows.
        var inserted = false;
        for (var j = subRows.length - 1; j >= 0; j--) {
          if (subRows[j].length == 0)
            continue;

          var insertedSlice = subRows[j][subRows[j].length - 1];
          if (slice.start < insertedSlice.start) {
            this.badSlices_.push(slice);
            inserted = true;
          }
          if (slice.start >= insertedSlice.start &&
              slice.end <= insertedSlice.end) {
            // Insert it into subRow j + 1.
            while (subRows.length <= j + 1)
              subRows.push([]);
            subRows[j + 1].push(slice);
            if (insertedSlice.subSlices)
              insertedSlice.subSlices.push(slice);
            inserted = true;
            break;
          }
        }
        if (inserted)
          continue;

        // Append it to subRow[0] as a root.
        subRows[0].push(slice);
      }

      return subRows;
    },

    areArrayContentsSame_: function(a, b) {
      if (!a || !b)
        return false;
      if (!a.length || !b.length)
        return false;
      if (a.length != b.length)
        return false;
      for (var i = 0; i < a.length; ++i) {
        if (a[i] != b[i])
          return false;
      }
      return true;
    }
  };

  return {
    TimelineSliceGroupTrack: TimelineSliceGroupTrack
  };
});
