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
tvcm.require('tvcm.ui.sunburst_chart');

tvcm.requireTemplate('tracing.sampling_summary_side_panel');

tvcm.exportTo('tracing', function() {
  var RequestSelectionChangeEvent = tracing.RequestSelectionChangeEvent;

  /**
     * @constructor
     */
  var CallTreeNode = function(name, category) {
    this.parent = undefined;
    this.name = name;
    this.category = category;
    this.selfTime = 0.0;
    this.children = [];
  }

  /**
   * @constructor
   */
  var Thread = function(thread) {
    this.thread = thread;
    this.rootNode = new CallTreeNode('root', 'root');
    this.rootCategories = {};
    this.sfToNode = {};
    this.sfToNode[0] = self.rootNode;
  }

  Thread.prototype = {
    getCallTreeNode: function(stackFrame) {
      if (stackFrame.id in this.sfToNode)
        return this.sfToNode[stackFrame.id];

      // Create & save the node.
      var newNode = new CallTreeNode(stackFrame.title, stackFrame.category);
      this.sfToNode[stackFrame.id] = newNode;

      // Add node to parent tree node.
      if (stackFrame.parentFrame) {
        var parentNode = this.getCallTreeNode(stackFrame.parentFrame);
        parentNode.children.push(newNode);
      } else {
        // Creating a root category node for each category helps group samples
        // that may be missing call stacks.
        var rootCategory = this.rootCategories[stackFrame.category];
        if (!rootCategory) {
          rootCategory =
              new CallTreeNode(stackFrame.category, stackFrame.category);
          this.rootNode.children.push(rootCategory);
          this.rootCategories[stackFrame.category] = rootCategory;
        }
        rootCategory.children.push(newNode);
      }
      return newNode;
    },

    addSample: function(sample) {
      var node = this.getCallTreeNode(sample.leafStackFrame);
      node.selfTime += sample.weight;
    }
  };

  function genCallTree(node, isRoot) {
    var ret = {
      category: node.category,
      name: node.name
    };

    if (isRoot || node.children.length > 0) {
      ret.children = [];
      for (var c = 0; c < node.children.length; c++)
        ret.children.push(genCallTree(node.children[c], false));
      if (node.selfTime > 0.0)
        ret.children.push({
          name: '<self>',
          category: ret.category,
          size: node.selfTime
        });
    }
    else {
      ret.size = node.selfTime;
    }
    if (isRoot)
      return ret.children;
    return ret;
  }

  // Create sunburst data from model data.
  function createSunburstData(model, rangeOfInterest) {
    // TODO(vmiura): Add selection.
    var threads = {};
    function getOrCreateThread(thread) {
      var ret = undefined;
      if (thread.tid in threads) {
        ret = threads[thread.tid];
      } else {
        ret = new Thread(thread);
        threads[thread.tid] = ret;
      }
      return ret;
    }

    // Process samples.
    var samples = model.samples;
    var rangeMin = rangeOfInterest.min;
    var rangeMax = rangeOfInterest.max;
    for (var i = 0; i < samples.length; i++) {
      var sample = samples[i];
      if (sample.start >= rangeMin && sample.start <= rangeMax)
        getOrCreateThread(sample.thread).addSample(sample);
    }

    // Generate sunburst data.
    var sunburstData = {
      name: '<All Threads>',
      category: 'root',
      children: []
    };
    for (var t in threads) {
      if (!threads.hasOwnProperty(t)) continue;
      var thread = threads[t];
      var threadData = {
        name: '<' + thread.thread.name + '>',
        category: 'Thread',
        children: genCallTree(thread.rootNode, true)
      };
      sunburstData.children.push(threadData);
    }
    return sunburstData;
  }

  // Create sunburst chart from model data.
  function createSunburstChart(model, rangeOfInterest) {
    // TODO(vmiura): Add selection.
    var sunburstData = createSunburstData(model, rangeOfInterest);
    var chart = new tvcm.ui.SunburstChart();
    chart.width = 800;
    chart.height = 800;
    chart.chartTitle = 'Sampling Summary';
    chart.data = sunburstData;
    return chart;
  }

  /**
   * @constructor
   */
  var SamplingSummarySidePanel =
      tvcm.ui.define('x-sample-summary-side-panel',
                     tracing.TimelineViewSidePanel);
  SamplingSummarySidePanel.textLabel = 'Sampling Summary';
  SamplingSummarySidePanel.supportsModel = function(m) {
    if (m == undefined) {
      return {
        supported: false,
        reason: 'Unknown tracing model'
      };
    }

    if (m.samples.length == 0) {
      return {
        supported: false,
        reason: 'No sampling data in trace'
      };
    }

    return {
      supported: true
    };
  };

  SamplingSummarySidePanel.prototype = {
    __proto__: tracing.TimelineViewSidePanel.prototype,

    decorate: function() {
      tracing.TimelineViewSidePanel.prototype.decorate.call(this);
      this.classList.add('x-sample-summary-side-panel');
      this.appendChild(tvcm.instantiateTemplate(
          '#x-sample-summary-side-panel-template'));

      this.rangeOfInterest_ = new tvcm.Range();
      this.chart_ = undefined;
    },

    get model() {
      return model_;
    },

    set model(model) {
      this.model_ = model;
      this.updateContents_();
    },

    get rangeOfInterest() {
      return this.rangeOfInterest_;
    },

    set rangeOfInterest(rangeOfInterest) {
      this.rangeOfInterest_ = rangeOfInterest;
      this.updateContents_();
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

      this.chart_ = createSunburstChart(this.model_, rangeOfInterest);
      resultArea.appendChild(this.chart_);
      this.chart_.setSize(this.chart_.getMinSize());
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(SamplingSummarySidePanel);

  return {
    SamplingSummarySidePanel: SamplingSummarySidePanel,
    createSunburstData: createSunburstData
  };
});
