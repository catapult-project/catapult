// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('system_stats.system_stats_instance_track');

base.require('base.sorted_array_utils');
base.require('tracing.tracks.heading_track');
base.require('tracing.tracks.object_instance_track');
base.require('tracing.color_scheme');
base.require('ui');

base.exportTo('system_stats', function() {

  var palette = tracing.getColorPalette();
  var highlightIdBoost = tracing.getColorPaletteHighlightIdBoost();

  var statCount;

  var excludedStats = {'meminfo': {
                        'pswpin': 0,
                        'pswpout': 0,
                        'pgmajfault': 0},
                      'diskinfo': {
                        'io': 0,
                        'io_time': 0,
                        'read_time': 0,
                        'reads': 0,
                        'reads_merged': 0,
                        'sectors_read': 0,
                        'sectors_written': 0,
                        'weighted_io_time': 0,
                        'write_time': 0,
                        'writes': 0,
                        'writes_merged': 0},
                      'swapinfo': {}
                      };

  /**
   * Tracks that display system stats data.
   *
   * @constructor
   * @extends {HeadingTrack}
   */

  var SystemStatsInstanceTrack = ui.define(
      'system-stats-instance-track', tracing.tracks.HeadingTrack);

  SystemStatsInstanceTrack.prototype = {

    __proto__: tracing.tracks.HeadingTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.HeadingTrack.prototype.decorate.call(this, viewport);
      this.classList.add('system-stats-instance-track');
      this.objectInstance_ = null;
    },

    set objectInstances(objectInstances) {
      if (!objectInstances) {
        this.objectInstance_ = [];
        return;
      }
      if (objectInstances.length != 1)
        throw new Error('Bad object instance count.');
      this.objectInstance_ = objectInstances[0];
      if (this.objectInstance_ !== null) {
        this.computeRates_(this.objectInstance_.snapshots);
        this.maxStats_ = this.computeMaxStats_(
            this.objectInstance_.snapshots);
      }
    },

    computeRates_: function(snapshots) {
      for (var i = 0; i < snapshots.length; i++) {
        var snapshot = snapshots[i];
        var stats = snapshot.getStats();
        var prevSnapshot;
        var prevStats;

        if (i == 0) {
          // Deltas will be zero.
          prevSnapshot = snapshots[0];
        } else {
          prevSnapshot = snapshots[i - 1];
        }
        prevStats = prevSnapshot.getStats();
        var timeIntervalSeconds = (snapshot.ts - prevSnapshot.ts) / 1000;
        // Prevent divide by zero.
        if (timeIntervalSeconds == 0)
          timeIntervalSeconds = 1;

        this.computeRatesRecursive_(prevStats, stats,
                                    timeIntervalSeconds);
      }
    },

    computeRatesRecursive_: function(prevStats, stats,
                                     timeIntervalSeconds) {
      for (var statName in stats) {
        if (stats[statName] instanceof Object) {
          this.computeRatesRecursive_(prevStats[statName],
                                      stats[statName],
                                      timeIntervalSeconds);
        } else {
          if (statName == 'sectors_read') {
            stats['bytes_read_per_sec'] = (stats['sectors_read'] -
                                           prevStats['sectors_read']) *
                                          512 / timeIntervalSeconds;
          }
          if (statName == 'sectors_written') {
            stats['bytes_written_per_sec'] =
                (stats['sectors_written'] -
                 prevStats['sectors_written']) *
                512 / timeIntervalSeconds;
          }
          if (statName == 'pgmajfault') {
            stats['pgmajfault_per_sec'] = (stats['pgmajfault'] -
                                           prevStats['pgmajfault']) /
                                          timeIntervalSeconds;
          }
          if (statName == 'pswpin') {
            stats['bytes_swpin_per_sec'] = (stats['pswpin'] -
                                            prevStats['pswpin']) *
                                           1000 / timeIntervalSeconds;
          }
          if (statName == 'pswpout') {
            stats['bytes_swpout_per_sec'] = (stats['pswpout'] -
                                             prevStats['pswpout']) *
                                            1000 / timeIntervalSeconds;
          }
        }
      }
    },

    computeMaxStats_: function(snapshots) {
      var maxStats = new Object();
      statCount = 0;

      for (var i = 0; i < snapshots.length; i++) {
        var snapshot = snapshots[i];
        var stats = snapshot.getStats();

        this.computeMaxStatsRecursive_(stats, maxStats,
                                       excludedStats);
      }

      return maxStats;
    },

    computeMaxStatsRecursive_: function(stats, maxStats, excludedStats) {
      for (var statName in stats) {
        if (stats[statName] instanceof Object) {
          if (!(statName in maxStats))
            maxStats[statName] = new Object();

          var excludedNested;
          if (excludedStats && statName in excludedStats)
            excludedNested = excludedStats[statName];
          else
            excludedNested = null;

          this.computeMaxStatsRecursive_(stats[statName],
                                         maxStats[statName],
                                         excludedNested);
        } else {
          if (excludedStats && statName in excludedStats)
            continue;
          if (!(statName in maxStats)) {
            maxStats[statName] = 0;
            statCount++;
          }
          if (stats[statName] > maxStats[statName])
            maxStats[statName] = stats[statName];
        }
      }
    },

    get height() {
      return window.getComputedStyle(this).height;
    },

    set height(height) {
      this.style.height = height;
    },

    draw: function(type, viewLWorld, viewRWorld) {
      switch (type) {
        case tracing.tracks.DrawType.SLICE:
          this.drawStatBars_(viewLWorld, viewRWorld);
          break;
      }
    },

    drawStatBars_: function(viewLWorld, viewRWorld) {
      var ctx = this.context();
      var pixelRatio = window.devicePixelRatio || 1;

      var bounds = this.getBoundingClientRect();
      var width = bounds.width * pixelRatio;
      var height = (bounds.height * pixelRatio) / statCount;

      // Culling parameters.
      var vp = this.viewport.currentDisplayTransform;

      // Scale by the size of the largest snapshot.
      var maxStats = this.maxStats_;

      var objectSnapshots = this.objectInstance_.snapshots;
      var lowIndex = base.findLowIndexInSortedArray(
          objectSnapshots,
          function(snapshot) {
            return snapshot.ts;
          },
          viewLWorld);

      // Assure that the stack with the left edge off screen still gets drawn
      if (lowIndex > 0)
        lowIndex -= 1;

      for (var i = lowIndex; i < objectSnapshots.length; ++i) {
        var snapshot = objectSnapshots[i];
        var trace = snapshot.getStats();
        var currentY = height;

        var left = snapshot.ts;
        if (left > viewRWorld)
          break;
        var leftView = vp.xWorldToView(left);
        if (leftView < 0)
          leftView = 0;

        // Compute the edges for the column graph bar.
        var right;
        if (i != objectSnapshots.length - 1) {
          right = objectSnapshots[i + 1].ts;
        } else {
          // If this is the last snaphot of multiple snapshots, use the width of
          // the previous snapshot for the width.
          if (objectSnapshots.length > 1)
            right = objectSnapshots[i].ts + (objectSnapshots[i].ts -
                    objectSnapshots[i - 1].ts);
          else
            // If there's only one snapshot, use max bounds as the width.
            right = this.objectInstance_.parent.model.bounds.max;
        }

        var rightView = vp.xWorldToView(right);
        if (rightView > width)
          rightView = width;

        // Floor the bounds to avoid a small gap between stacks.
        leftView = Math.floor(leftView);
        rightView = Math.floor(rightView);

        // Descend into nested stats.
        this.drawStatBarsRecursive_(snapshot,
                                    leftView,
                                    rightView,
                                    height,
                                    trace,
                                    maxStats,
                                    currentY);

        if (i == lowIndex)
          this.drawStatNames_(leftView, height, currentY, maxStats);
      }
      ctx.lineWidth = 1;
    },

    drawStatBarsRecursive_: function(snapshot,
                                     leftView,
                                     rightView,
                                     height,
                                     stats,
                                     maxStats,
                                     currentY) {
      var ctx = this.context();

      for (var statName in maxStats) {
        if (stats[statName] instanceof Object) {
          // Use the y-position returned from the recursive call.
          currentY = this.drawStatBarsRecursive_(snapshot,
                                                 leftView,
                                                 rightView,
                                                 height,
                                                 stats[statName],
                                                 maxStats[statName],
                                                 currentY);
        } else {
          var maxStat = maxStats[statName];

          // Draw a bar for the stat. The height of the bar is scaled
          // against the largest value of the stat across all snapshots.

          // Selected snapshots get a lighter color.
          var colorId = snapshot.selected ?
              snapshot.objectInstance.colorId + highlightIdBoost :
              snapshot.objectInstance.colorId;
          ctx.fillStyle = palette[colorId + Math.round(currentY / height)];
          var barHeight;

          if (maxStat > 0) {
            barHeight = height * Math.max(stats[statName], 0) / maxStat;
          } else {
            barHeight = 0;
          }

          ctx.fillRect(leftView, currentY - barHeight,
                       Math.max(rightView - leftView, 1), barHeight);

          currentY += height;
        }
      }

      // Return the updated y-position.
      return currentY;
    },

    drawStatNames_: function(leftView, height, currentY, maxStats) {
      var ctx = this.context();

      ctx.textAlign = 'end';
      ctx.font = '12px Arial';
      ctx.fillStyle = '#000000';
      for (var statName in maxStats) {
        if (maxStats[statName] instanceof Object) {
          currentY = this.drawStatNames_(leftView, height, currentY,
                                         maxStats[statName]);
        } else {
          ctx.fillText(statName, leftView - 10, currentY - height / 4);
          currentY += height;
        }
      }

      return currentY;
    },

    addEventsToTrackMap: function(eventToTrackMap) {
      var objectSnapshots = this.objectInstance_.snapshots;
      objectSnapshots.forEach(function(obj) {
        eventToTrackMap.addEvent(obj, this);
      }, this);
    },

    /**
     * Used to hit-test clicks in the graph.
     */
    addIntersectingItemsInRangeToSelectionInWorldSpace: function(
        loWX, hiWX, viewPixWidthWorld, selection) {
      function onSnapshot(snapshot) {
        selection.push(snapshot);
      }

      var snapshots = this.objectInstance_.snapshots;
      var maxBounds = this.objectInstance_.parent.model.bounds.max;

      base.iterateOverIntersectingIntervals(
          snapshots,
          function(x) { return x.ts; },
          function(x, i) {
            if (i == snapshots.length - 1) {
              if (snapshots.length == 1)
                return maxBounds;

              return snapshots[i].ts - snapshots[i - 1].ts;
            }

            return snapshots[i + 1].ts - snapshots[i].ts;
          },
          loWX, hiWX,
          onSnapshot);
    },

    /**
     * Add the item to the left or right of the provided item, if any, to the
     * selection.
     *
     * @param {slice} The current slice.
     * @param {Number} offset Number of slices away from the object to look.
     * @param {Selection} selection The selection to add an event to, if found.
     * @return {boolean} Whether an event was found.
     * @private
     */
    addItemNearToProvidedEventToSelection: function(event, offset, selection) {
      if (!(event instanceof tracing.trace_model.ObjectSnapshot))
        throw new Error('Unrecognized event');
      var objectSnapshots = this.objectInstance_.snapshots;
      var index = objectSnapshots.indexOf(event);
      var newIndex = index + offset;
      if (newIndex >= 0 && newIndex < objectSnapshots.length) {
        selection.push(objectSnapshots[newIndex]);
        return true;
      }
      return false;
    },

    addAllObjectsMatchingFilterToSelection: function(filter, selection) {
    },

    addClosestEventToSelection: function(worldX, worldMaxDist, loY, hiY,
                                         selection) {
      var snapshot = base.findClosestElementInSortedArray(
          this.objectInstance_.snapshots,
          function(x) { return x.ts; },
          worldX,
          worldMaxDist);

      if (!snapshot)
        return;

      selection.push(snapshot);
    }
  };

  tracing.tracks.ObjectInstanceTrack.register(
      'system_stats', SystemStatsInstanceTrack);

  return {
    SystemStatsInstanceTrack: SystemStatsInstanceTrack
  };
});
