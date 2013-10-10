// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.sorted_array_utils');
base.require('base.utils');
base.require('tracing.analysis.generic_object_view');
base.require('tracing.analysis.slice_view');
base.require('tracing.analysis.util');
base.require('tracing.analysis.analysis_link');
base.require('tracing.color_scheme');
base.requireTemplate('tracing.analysis.thread_time_slice_view');

base.exportTo('tracing.analysis', function() {
  var tsRound = tracing.analysis.tsRound;

  /**
   * @constructor
   */
  var ThreadTimeSliceView = ui.define(
      'thread-time-slice-view', tracing.analysis.SliceView);

  ThreadTimeSliceView.prototype = {
    __proto__: tracing.analysis.SliceView.prototype,

    decorate: function() {
      tracing.analysis.SliceView.prototype.decorate.call(this);
      this.classList.add('thread-time-slice-view');
    },

    updateContents: function() {
      this.textContent = '';
      this.appendChild(
          base.instantiateTemplate('#thread-time-slice-view-template'));

      var timeSlice = this.slice;
      var thread = timeSlice.thread;

      this.querySelector('#state').textContent = timeSlice.title;
      var stateColor = tracing.getColorPalette()[timeSlice.colorId];
      this.querySelector('#state').style.backgroundColor = stateColor;

      this.querySelector('#process-name').textContent =
          thread.parent.userFriendlyName;
      this.querySelector('#thread-name').textContent = thread.userFriendlyName;

      this.querySelector('#start').textContent =
          tsRound(timeSlice.start) + 'ms';
      this.querySelector('#duration').textContent =
          tsRound(timeSlice.duration) + 'ms';
      var onCpuEl = this.querySelector('#on-cpu');
      var runningInsteadEl = this.querySelector('#running-instead');
      if (timeSlice.cpuOnWhichThreadWasRunning) {
        runningInsteadEl.parentElement.removeChild(runningInsteadEl);
        var cpuLink = new tracing.analysis.AnalysisLink();
        cpuLink.textContent =
            timeSlice.cpuOnWhichThreadWasRunning.userFriendlyName;
        cpuLink.selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.push(timeSlice.getAssociatedCpuSlice());
          return selection;
        }.bind(this);
        onCpuEl.appendChild(cpuLink);
      } else {
        onCpuEl.parentElement.removeChild(onCpuEl);

        var cpuSliceThatTookCpu = timeSlice.getCpuSliceThatTookCpu();
        if (cpuSliceThatTookCpu) {
          var cpuLink = new tracing.analysis.AnalysisLink();
          if (cpuSliceThatTookCpu.thread)
            cpuLink.textContent = cpuSliceThatTookCpu.thread.userFriendlyName;
          else
            cpuLink.textContent = cpuSliceThatTookCpu.title;
          cpuLink.selectionGenerator = function() {
            var selection = new tracing.Selection();
            selection.push(cpuSliceThatTookCpu);
            return selection;
          }.bind(this);
          runningInsteadEl.appendChild(cpuLink);
        } else {
          runningInsteadEl.parentElement.removeChild(runningInsteadEl);
        }
      }

      var argsEl = this.querySelector('#args');
      if (base.dictionaryKeys(timeSlice.args).length > 0) {
        var argsView = new tracing.analysis.GenericObjectView();
        argsView.object = timeSlice.args;
        argsEl.appendChild(argsView);
      } else {
        argsEl.parentElement.removeChild(argsEl);
      }
    }
  };

  tracing.analysis.SliceView.register(
      'tracing.analysis.ThreadTimeSlice', ThreadTimeSliceView);

  return {
    ThreadTimeSliceView: ThreadTimeSliceView
  };
});
