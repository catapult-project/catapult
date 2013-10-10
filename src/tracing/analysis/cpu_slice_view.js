// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.utils');
base.require('tracing.analysis.slice_view');
base.require('tracing.analysis.util');
base.require('tracing.analysis.analysis_link');
base.requireTemplate('tracing.analysis.cpu_slice_view');

base.exportTo('tracing.analysis', function() {
  var tsRound = tracing.analysis.tsRound;

  /**
   * @constructor
   */
  var CpuSliceView = ui.define('cpu-slice-view', tracing.analysis.SliceView);

  CpuSliceView.prototype = {
    __proto__: tracing.analysis.SliceView.prototype,

    decorate: function() {
      tracing.analysis.SliceView.prototype.decorate.call(this);
      this.classList.add('cpu-slice-view');
    },

    updateContents: function() {
      this.textContent = '';
      this.appendChild(base.instantiateTemplate('#cpu-slice-view-template'));

      var cpuSlice = this.slice;
      var thread = cpuSlice.threadThatWasRunning;

      if (thread) {
        this.querySelector('#process-name').textContent =
            thread.parent.userFriendlyName;
        this.querySelector('#thread-name').textContent =
            thread.userFriendlyName;
      } else {
        this.querySelector('#process-name').parentElement.style.display =
            'none';
        this.querySelector('#thread-name').textContent = cpuSlice.title;
      }
      this.querySelector('#start').textContent = tsRound(cpuSlice.start) + 'ms';
      this.querySelector('#duration').textContent =
          tsRound(cpuSlice.duration) + 'ms';
      var runningThreadEl = this.querySelector('#running-thread');
      var timeSlice = cpuSlice.getAssociatedTimeslice();
      if (!timeSlice) {
        runningThreadEl.parentElement.style.display = 'none';
      } else {
        var threadLink = new tracing.analysis.AnalysisLink();
        threadLink.textContent = 'Click to select';
        threadLink.selectionGenerator = function() {
          var selection = new tracing.Selection();
          selection.push(timeSlice);
          return selection;
        }.bind(this);
        runningThreadEl.appendChild(threadLink);
      }
    }
  };

  tracing.analysis.SliceView.register(
      'tracing.analysis.CpuSlice', CpuSliceView);

  return {
    CpuSliceView: CpuSliceView
  };
});
