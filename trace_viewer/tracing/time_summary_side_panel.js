// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.analysis.util');
tvcm.require('tracing.selection');
tvcm.require('tracing.timeline_view_side_panel');
tvcm.require('tvcm.iteration_helpers');
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

  function getSlicesInsideRange(rangeOfInterest, slices) {
    var slicesInFilterRange = [];
    for (var i = 0; i < slices.length; i++) {
      var slice = slices[i];
      if (rangeOfInterest.containsExplicitRange(slice.start, slice.end))
        slicesInFilterRange.push(slice);
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
        // Only report cpu-duration if we have it for all events.
        //
        // A cpu_duration of 0 is valid, so this only returns 0 if it is
        // None.
        if (x.cpuDuration === undefined) {
          if (x.duration === undefined)
            continue;
          return 0;
        } else {
          cpuDuration += x.cpuDuration;
        }
      }

      var cpuOverhead = tvcm.sum(function(x) {
        return getCpuTimeOverheadForEvent(x);
      }, this.allSlices);
      return cpuDuration - cpuOverhead;
    },

    appendThreadSlices: function(rangeOfInterest, thread) {
      var tmp = getSlicesInsideRange(
          rangeOfInterest, thread.sliceGroup.slices);
      tmp.forEach(function(slice) {
        this.allSlices.push(slice);
      }, this);
      tmp = getSlicesInsideRange(
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

      // Build chart data.
      var groupNames = tvcm.dictionaryKeys(resultsByGroupName);
      groupNames.sort();


      var getValueFromGroup = function(group) {
        if (this.groupingUnit_ == WALL_TIME_GROUPING_UNIT)
          return group.wallTime;
        return group.cpuTime;
      }.bind(this);

      var data = [];
      groupNames.forEach(function(groupName) {
        var resultsForGroup = resultsByGroupName[groupName];
        var value = getValueFromGroup(resultsForGroup);
        if (value === 0)
          return;
        data.push({
          label: groupName,
          value: value,
          valueText: tsRound(value) + 'ms',
          onClick: function() {
            var event = new tracing.RequestSelectionChangeEvent();
            event.selection = new tracing.Selection(resultsForGroup.allSlices);
            event.selection.timeSummaryGroupName = groupName;
            this.dispatchEvent(event);
          }.bind(this)
        });
      }, this);

      if (data.length == 0) {
        resultArea.appendChild(tvcm.ui.createSpan({textContent: 'No data'}));
        return;
      }

      var summaryText = document.createElement('div');
      summaryText.appendChild(tvcm.ui.createSpan({
        textContent: 'Total ' + this.groupingUnit_ + ': ',
        bold: true}));
      summaryText.appendChild(tvcm.ui.createSpan({
        textContent: tsRound(getValueFromGroup(allGroup)) + 'ms'
      }));
      resultArea.appendChild(summaryText);

      this.chart_ = new tvcm.ui.PieChart();
      this.chart_.width = 400;
      this.chart_.height = 400;
      this.chart_.chartTitle = this.groupingUnit_ + ' breakdown by ' +
          this.groupBy_;
      this.chart_.data = data;
      this.chart_.addEventListener('click', function() {
        var event = new tracing.RequestSelectionChangeEvent();
        event.selection = new tracing.Selection([]);
        this.dispatchEvent(event);
      });

      resultArea.appendChild(this.chart_);
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
    ResultsForGroup: ResultsForGroup,
    TimeSummarySidePanel: TimeSummarySidePanel
  };
});
