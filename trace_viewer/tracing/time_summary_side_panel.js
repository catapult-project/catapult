// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.analysis.util');
tvcm.require('tracing.selection');
tvcm.require('tracing.timeline_view_side_panel');
tvcm.require('tvcm.iteration_helpers');
tvcm.require('tvcm.statistics');
tvcm.require('tvcm.ui.dom_helpers');
tvcm.require('tvcm.ui.pie_chart');

tvcm.requireTemplate('tracing.time_summary_side_panel');

tvcm.exportTo('tracing', function() {
  var ThreadSlice = tracing.trace_model.ThreadSlice;

  var OVERHEAD_TRACE_CATEGORY = 'trace_event_overhead';
  var OVERHEAD_TRACE_NAME = 'overhead';

  var tsRound = tracing.analysis.tsRound;

  var RequestSelectionChangeEvent = tracing.RequestSelectionChangeEvent;

  function getWallTimeOverheadForEvent(event) {
    if (event.category == OVERHEAD_TRACE_CATEGORY &&
        event.name == OVERHEAD_TRACE_NAME) {
      return event.duration;
    }
    return 0;
  }

  function getCpuTimeOverheadForEvent(event) {
    if (event.category == OVERHEAD_TRACE_CATEGORY &&
        event.cpuDuration) {
      return event.cpuDuration;
    }
    return 0;
  }

  function getSlicesIntersectingRange(rangeOfInterest, slices) {
    var slicesInFilterRange = [];
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (rangeOfInterest.intersectsExplicitRange(slice.start, slice.end))
        slicesInFilterRange.push(slice);
    }
    return slicesInFilterRange;
  }

  /**
   * This function takes an array of groups and merges smaller groups into the
   * provided 'Other' group item such that the remaining items are ready for
   * pie-chart consumption. Otherwise, the pie chart gets overwhelmed with tons
   * of little slices.
   */
  function trimPieChartData(groups, otherGroup, getValue) {
    // Copy the array so it can be mutated.
    groups = groups.filter(function(d) {
      return getValue(d) != 0;
    });

    // Figure out total array range.
    var sum = tvcm.Statistics.sum(groups, getValue);

    // Sort by value.
    function compareByValue(a, b) {
      return getValue(a) - getValue(b);
    }
    groups.sort(compareByValue);

    // Now start fusing elements until none are less than threshold in size.
    var thresshold = 0.05 * sum;
    while (groups.length > 1) {
      var group = groups[0];
      if (getValue(group) >= thresshold)
        break;

      var v = getValue(group);
      if (v + getValue(otherGroup) > thresshold)
        break;

      // Remove the group from the list and add it to the 'Other' group.
      groups.splice(0, 1);
      otherGroup.appendGroupContents(group);
    }

    // Final return.
    if (getValue(otherGroup) > 0)
      groups.push(otherGroup);

    groups.sort(compareByValue);

    return groups;
  }

  function createPieChartFromResultGroups(groups, title, getValue) {
    var chart = new tvcm.ui.PieChart();

    // Build chart data.
    var data = [];
    groups.forEach(function(resultsForGroup) {
      var value = getValue(resultsForGroup);
      if (value === 0)
        return;
      data.push({
        label: resultsForGroup.name,
        value: value,
        valueText: tsRound(value) + 'ms',
        onClick: function() {
          var event = new tracing.RequestSelectionChangeEvent();
          event.selection = new tracing.Selection(resultsForGroup.allSlices);
          event.selection.timeSummaryGroupName = resultsForGroup.name;
          chart.dispatchEvent(event);
        }
      });
    });

    chart.chartTitle = title;
    chart.data = data;
    return chart;
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
      var wallSum = tvcm.Statistics.sum(
          this.topLevelSlices, function(x) { return x.duration; });
      return wallSum;
    },

    get cpuTime() {
      var cpuDuration = 0;
      for (var i = 0; i < this.topLevelSlices.length; i++) {
        var x = this.topLevelSlices[i];
        // Only report thread-duration if we have it for all events.
        //
        // A thread_duration of 0 is valid, so this only returns 0 if it is
        // None.
        if (x.cpuDuration === undefined) {
          if (x.duration === undefined)
            continue;
          return 0;
        } else {
          cpuDuration += x.cpuDuration;
        }
      }

      return cpuDuration;
    },

    appendGroupContents: function(group) {
      if (group.model != this.model)
        throw new Error('Models must be the same');

      group.allSlices.forEach(function(slice) {
        this.allSlices.push(slice);
      }, this);
      group.topLevelSlices.forEach(function(slice) {
        this.topLevelSlices.push(slice);
      }, this);
    },

    appendThreadSlices: function(rangeOfInterest, thread) {
      var tmp = getSlicesIntersectingRange(
          rangeOfInterest, thread.sliceGroup.slices);
      tmp.forEach(function(slice) {
        this.allSlices.push(slice);
      }, this);
      tmp = getSlicesIntersectingRange(
          rangeOfInterest, thread.sliceGroup.topLevelSlices);
      tmp.forEach(function(slice) {
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

      this.rangeOfInterest_ = new tvcm.Range();
      this.selection_ = undefined;
      this.groupBy_ = GROUP_BY_PROCESS_NAME;
      this.chart_ = undefined;

      var toolbarEl = this.querySelector('toolbar');
      toolbarEl.appendChild(tvcm.ui.createSelector(
          this, 'groupBy',
          'timeSummarySidePanel.groupBy', this.groupBy_,
          [{label: 'Group by process', value: GROUP_BY_PROCESS_NAME},
           {label: 'Group by thread', value: GROUP_BY_THREAD_NAME}
          ]));

      this.groupingUnit_ = CPU_TIME_GROUPING_UNIT;
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
        return thread.name ? thread.name : thread.userFriendlyName;

      if (this.groupBy_ == GROUP_BY_PROCESS_NAME)
        return thread.parent.userFriendlyName;
    },

    updateContents_: function() {
      var resultArea = this.querySelector('result-area');
      this.chart_ = undefined;
      resultArea.textContent = '';

      if (this.model_ === undefined)
        return;

      var rangeOfInterest;
      if (this.rangeOfInterest_.isEmpty)
        rangeOfInterest = this.model_.bounds;
      else
        rangeOfInterest = this.rangeOfInterest_;

      var allGroup = new ResultsForGroup(this.model_, 'all');
      var resultsByGroupName = {};
      this.model_.getAllThreads().forEach(function(thread) {
        var groupName = this.getGroupNameForThread_(thread);
        if (resultsByGroupName[groupName] === undefined) {
          resultsByGroupName[groupName] = new ResultsForGroup(
              this.model_, groupName);
        }
        resultsByGroupName[groupName].appendThreadSlices(
            rangeOfInterest, thread);

        allGroup.appendThreadSlices(rangeOfInterest, thread);
      }, this);

      // Helper function for working with the produced group.
      var getValueFromGroup = function(group) {
        if (this.groupingUnit_ == WALL_TIME_GROUPING_UNIT)
          return group.wallTime;
        return group.cpuTime;
      }.bind(this);

      // Create summary.
      var summaryText = document.createElement('div');
      summaryText.appendChild(tvcm.ui.createSpan({
        textContent: 'Total ' + this.groupingUnit_ + ': ',
        bold: true}));
      summaryText.appendChild(tvcm.ui.createSpan({
        textContent: tsRound(getValueFromGroup(allGroup)) + 'ms'
      }));
      resultArea.appendChild(summaryText);

      // Create the actual chart.
      var otherGroup = new ResultsForGroup(this.model_, 'Other');
      var groups = trimPieChartData(
          tvcm.dictionaryValues(resultsByGroupName),
          otherGroup,
          getValueFromGroup);
      if (groups.length == 0) {
        resultArea.appendChild(tvcm.ui.createSpan({textContent: 'No data'}));
        return undefined;
      }

      this.chart_ = createPieChartFromResultGroups(
          groups,
          this.groupingUnit_ + ' breakdown by ' + this.groupBy_,
          getValueFromGroup);
      resultArea.appendChild(this.chart_);
      this.chart_.addEventListener('click', function() {
        var event = new tracing.RequestSelectionChangeEvent();
        event.selection = new tracing.Selection([]);
        this.dispatchEvent(event);
      });
      this.chart_.setSize(this.chart_.getMinSize());
    },

    get selection() {
      return selection_;
    },

    set selection(selection) {
      this.selection_ = selection;

      if (this.chart_ === undefined)
        return;

      if (selection.timeSummaryGroupName) {
        this.chart_.highlightedLegendKey =
            selection.timeSummaryGroupName;
      } else {
        this.chart_.highlightedLegendKey = undefined;
      }
    },

    get rangeOfInterest() {
      return this.rangeOfInterest_;
    },

    set rangeOfInterest(rangeOfInterest) {
      this.rangeOfInterest_ = rangeOfInterest;
      this.updateContents_();
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(TimeSummarySidePanel);

  return {
    trimPieChartData: trimPieChartData,
    createPieChartFromResultGroups: createPieChartFromResultGroups,
    ResultsForGroup: ResultsForGroup,
    TimeSummarySidePanel: TimeSummarySidePanel
  };
});
