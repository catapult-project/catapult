// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.sorted_array_utils');
base.require('tracing.tracks.container_track');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  /**
   * A track that displays a SliceGroup.
   * @constructor
   * @extends {ContainerTrack}
   */

  var SliceGroupTrack = ui.define(
      'slice-group-track', tracing.tracks.ContainerTrack);

  SliceGroupTrack.prototype = {

    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.ContainerTrack.prototype.decorate.call(this, viewport);
      this.classList.add('slice-group-track');
      this.tooltip_ = '';
      this.heading_ = '';
    },

    get group() {
      return this.group_;
    },

    set group(g) {
      this.group_ = g;
      this.updateContents_();
    },

    get heading() {
      return this.heading_;
    },

    set heading(h) {
      this.heading_ = h;
      this.updateContents_();
    },

    get tooltip() {
      return this.tooltip_;
    },

    set tooltip(t) {
      this.tooltip_ = t;
      this.updateContents_();
    },

    set decorateHit(f) {
      this.decorateHit_ = f;
      this.updateContents_();
    },

    addSliceTrack_: function(slices) {
      var track = new tracing.tracks.SliceTrack(this.viewport);
      track.slices = slices;
      track.decorateHit = this.decorateHit_;
      track.categoryFilter_ = this.categoryFilter;
      this.appendChild(track);
      return track;
    },

    get subRows() {
      return base.asArray(this.children).map(function(sliceTrack) {
        return sliceTrack.slices;
      });
    },

    get hasVisibleContent() {
      return this.children.length > 0;
    },

    updateContents_: function() {
      if (!this.group_) {
        this.updateHeadingAndTooltip_();
        return;
      }

      var slices = tracing.filterSliceArray(this.categoryFilter,
                                            this.group_.slices);
      if (this.areArrayContentsSame_(this.filteredSlices_, slices)) {
        this.updateHeadingAndTooltip_();
        return;
      }

      this.filteredSlices_ = slices;

      this.detach();
      if (!slices.length)
        return;
      var subRows = this.buildSubRows_(slices);
      for (var srI = 0; srI < subRows.length; srI++) {
        var subRow = subRows[srI];
        if (!subRow.length)
          continue;
        this.addSliceTrack_(subRow);
      }
      this.updateHeadingAndTooltip_();
    },

    updateHeadingAndTooltip_: function() {
      if (!this.firstChild)
        return;
      this.firstChild.heading = this.heading_;
      this.firstChild.tooltip = this.tooltip_;
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
    SliceGroupTrack: SliceGroupTrack
  };
});
