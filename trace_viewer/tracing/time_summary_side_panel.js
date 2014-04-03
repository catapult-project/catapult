// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.timeline_view_side_panel');
tvcm.require('tvcm.iteration_helpers');
tvcm.require('tvcm.ui.pie_chart');
tvcm.require('tvcm.ui.dom_helpers');

tvcm.requireTemplate('tracing.time_summary_side_panel');

tvcm.exportTo('tracing', function() {
  var ThreadSlice = tracing.trace_model.ThreadSlice;

  var OVERHEAD_TRACE_CATEGORY = "trace_event_overhead"
  var OVERHEAD_TRACE_NAME = "overhead"

  function getWallTimeOverheadForEvent(event) {
    if (event.category == OVERHEAD_TRACE_CATEGORY &&
        event.name == OVERHEAD_TRACE_NAME) {
      return event.duration
    }
    return 0
  }

  function getCpuTimeOverheadForEvent(event) {
    if (event.category == OVERHEAD_TRACE_CATEGORY &&
        event.threadDuration) {
      return event.threadDuration
    }
    return 0
  }

  function getSlicesInsideRange(filterRange, slices) {
    var slicesInFilterRange = []
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (filterRange.containsExplicitRange(slice.start, slice.end))
        slicesInFilterRange.push(slice)
    }
    return slicesInFilterRange;
  }

  /**
   * @constructor
   */
  function ResultsForGroup(model, name) {
    this.model = model;
    this.name = name;
    this.topLevelSlices = [];
    this.allSlices = [];
  }

  ResultsForGroup.prototype = {
    get wallTime() {
      var wallSum = tvcm.sum(function(x) { return x.duration; },
                             this.topLevelSlices);
      var wallOverheadSum = tvcm.sum(function(x) {
        return getWallTimeOverheadForEvent(x);
      },this.allSlices);
      return wallSum - wallOverheadSum;
    },

    get cpuTime() {
      var cpuDuration = 0;
      for (var i = 0; i < this.topLevelSlices.length; i++) {
        var x = this.topLevelSlices[i];
        // Only report thread-duration if we have it for all events.
        //
        // A thread_duration of 0 is valid, so this only returns 0 if it is
        // None.
        if (x.threadDuration === undefined) {
          if (x.duration === undefined)
            continue
          return 0;
        } else {
          cpuDuration += x.threadDuration
        }
      }

      var cpuOverhead = tvcm.sum(function(x) {
        return getCpuTimeOverheadForEvent(x);
      }, this.allSlices);
      return cpuDuration - cpuOverhead
    },

    appendThreadSlices: function(filterRange, thread) {
      getSlicesInsideRange(
          filterRange, thread.sliceGroup.slices).forEach(
              function(slice) {
                this.allSlices.push(slice);
              }, this);
      getSlicesInsideRange(
          filterRange, thread.sliceGroup.topLevelSlices).forEach(
              function(slice) {
                this.topLevelSlices.push(slice);
              }, this);
    }
  };

  var GROUP_BY_PROCESS_NAME = 'process';
  var GROUP_BY_THREAD_NAME = 'thread';

  var WALL_TIME_GROUPING_UNIT = 'Wall time';
  var CPU_TIME_GROUPING_UNIT = 'CPU time';

  /**
   * @constructor
   */
  var TimeSummarySidePanel = tvcm.ui.define('x-time-summary-side-panel',
                                            tracing.TimelineViewSidePanel);
  TimeSummarySidePanel.textLabel = 'Thread Times';
  TimeSummarySidePanel.supportsModel = function(m) {
    return {
      supported: true
    };
  };

  TimeSummarySidePanel.prototype = {
    __proto__: tracing.TimelineViewSidePanel.prototype,

    decorate: function() {
      tracing.TimelineViewSidePanel.prototype.decorate.call(this);
      this.classList.add('x-time-summary-side-panel');
      this.appendChild(tvcm.instantiateTemplate(
          '#x-time-summary-side-panel-template'));

      this.groupBy_ = GROUP_BY_PROCESS_NAME;

      var toolbarEl = this.querySelector('toolbar');
      toolbarEl.appendChild(tvcm.ui.createSelector(
        this, 'groupBy',
        'timeSummarySidePanel.groupBy', this.groupBy_,
        [{label: 'Group by process', value: GROUP_BY_PROCESS_NAME},
         {label: 'Group by thread', value: GROUP_BY_THREAD_NAME}
         ]));

      this.groupingUnit_ = WALL_TIME_GROUPING_UNIT;
      toolbarEl.appendChild(tvcm.ui.createSelector(
        this, 'groupingUnit',
        'timeSummarySidePanel.groupingUnit', this.groupingUnit_,
        [{label: 'Wall time', value: WALL_TIME_GROUPING_UNIT},
         {label: 'CPU time', value: CPU_TIME_GROUPING_UNIT}
         ]));
    },

    get model() {
      return model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateContents_();
    },

    get groupBy() {
      return groupBy_;
    },

    set groupBy(groupBy) {
      this.groupBy_ = groupBy;
      this.updateContents_();
    },

    get groupingUnit() {
      return groupingUnit_;
    },

    set groupingUnit(groupingUnit) {
      this.groupingUnit_ = groupingUnit;
      this.updateContents_();
    },

    getGroupNameForThread_: function(thread) {
      if (this.groupBy_ == GROUP_BY_THREAD_NAME)
        return thread.name;

      if (this.groupBy_ == GROUP_BY_PROCESS_NAME)
        return thread.parent.userFriendlyName;
    },

    updateContents_: function() {
      var resultArea = this.querySelector('result-area');
      resultArea.textContent = '';

      if (this.model_ === undefined)
        return;

      // TODO(nduca): Use the timeline view's interest region
      // for bounds instead of the world bounds.
      var filterRange = this.model_.bounds;

      var resultsByGroupName = {};
      this.model_.getAllThreads().forEach(function(thread) {
        var groupName = this.getGroupNameForThread_(thread);
        if (resultsByGroupName[groupName] === undefined) {
          resultsByGroupName[groupName] = new ResultsForGroup(
              this.model_, groupName);
        }
        resultsByGroupName[groupName].appendThreadSlices(filterRange, thread);
      }, this);

      // Build chart data.
      var groupNames = tvcm.dictionaryKeys(resultsByGroupName);
      groupNames.sort();

      var data = [];
      groupNames.forEach(function(groupName) {
        var resultsForGroup = resultsByGroupName[groupName];
        var value;
        if (this.groupingUnit_ == WALL_TIME_GROUPING_UNIT)
          value = resultsForGroup.wallTime;
        else
          value = resultsForGroup.cpuTime;
        if (value === 0)
          return;
        data.push({
          label: groupName,
          value: value
        });
      }, this);
      if (data.length == 0) {
        resultArea.appendChild(tvcm.ui.createSpan({textContent: 'No data'}));
        return;
      }
      var chart = new tvcm.ui.PieChart();
      chart.width = 400;
      chart.height = 400;
      chart.chartTitle = this.groupingUnit_ + ' breakdown by ' + this.groupBy_;
      chart.data = data;
      resultArea.appendChild(chart);
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(TimeSummarySidePanel);

  return {
    ResultsForGroup: ResultsForGroup,
    TimeSummarySidePanel: TimeSummarySidePanel
  };
});
