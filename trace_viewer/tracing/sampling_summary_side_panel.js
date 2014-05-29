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
tvcm.require('tvcm.ui.sortable_table');
tvcm.require('tvcm.ui.sunburst_chart');

tvcm.requireTemplate('tracing.sampling_summary_side_panel');

tvcm.exportTo('tracing', function() {
  var RequestSelectionChangeEvent = tracing.RequestSelectionChangeEvent;
  var getColorOfKey = tvcm.ui.getColorOfKey;

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

  function getSampleTypes(model, rangeOfInterest) {
    var sampleDict = {};
    var samples = model.samples;
    var rangeMin = rangeOfInterest.min;
    var rangeMax = rangeOfInterest.max;
    for (var i = 0; i < samples.length; i++) {
      var sample = samples[i];
      if (sample.start >= rangeMin && sample.start <= rangeMax)
        sampleDict[sample.title] = null;
    }
    return Object.keys(sampleDict);
  }

  // Create sunburst data from model data.
  function createSunburstData(model, rangeOfInterest, sampleType) {
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
      if (sample.start >= rangeMin &&
          sample.start <= rangeMax &&
          sample.title == sampleType)
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
        name: 'Thread ' + thread.thread.tid + ': ' + thread.thread.name,
        category: 'Thread',
        children: genCallTree(thread.rootNode, true)
      };
      sunburstData.children.push(threadData);
    }
    return sunburstData;
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

      this.sampleType_ = undefined;
      this.sampleTypeSelector_ = undefined;
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

    get sampleType() {
      return this.sampleType_;
    },

    set sampleType(type) {
      this.sampleType_ = type;
      if (this.sampleTypeSelector_)
        this.sampleTypeSelector_.selectedValue = type;
      this.updateResultArea_();
    },

    get rangeOfInterest() {
      return this.rangeOfInterest_;
    },

    set rangeOfInterest(rangeOfInterest) {
      this.rangeOfInterest_ = rangeOfInterest;
      this.updateContents_();
    },

    updateCallees_: function(d) {
      // Update callee table.
      var that = this;
      var table = document.createElement('table');

      // Add column styles.
      var col0 = document.createElement('col');
      var col1 = document.createElement('col');
      col0.className += 'x-col-numeric';
      col1.className += 'x-col-numeric';
      table.appendChild(col0);
      table.appendChild(col1);

      // Add headers.
      var thead = table.createTHead();
      var headerRow = thead.insertRow(0);
      headerRow.style.backgroundColor = '#888';
      headerRow.insertCell(0).appendChild(document.createTextNode('Samples'));
      headerRow.insertCell(1).appendChild(document.createTextNode('Percent'));
      headerRow.insertCell(2).appendChild(document.createTextNode('Symbol'));

      // Add body.
      var tbody = table.createTBody();
      if (d.children) {
        for (var i = 0; i < d.children.length; i++) {
          var c = d.children[i];
          var row = tbody.insertRow(i);
          var bgColor = getColorOfKey(c.category);
          if (bgColor == undefined)
            bgColor = '#444444';
          row.style.backgroundColor = bgColor;
          var cell0 = row.insertCell(0);
          var cell1 = row.insertCell(1);
          var cell2 = row.insertCell(2);
          cell0.className += 'x-td-numeric';
          cell1.className += 'x-td-numeric';
          cell0.appendChild(document.createTextNode(c.value.toString()));
          cell1.appendChild(document.createTextNode(
              (100 * c.value / d.value).toFixed(2) + '%'));
          cell2.appendChild(document.createTextNode(c.name));
        }
      }

      // Make it sortable.
      tvcm.ui.SortableTable.decorate(table);

      var calleeArea = that.querySelector('x-callees');
      calleeArea.textContent = '';
      calleeArea.appendChild(table);
    },

    updateHighlight_: function(d) {
      var that = this;

      // Update explanation.
      var percent = 100.0;
      if (that.chart_.selectedNode != null)
        percent = 100.0 * d.value / that.chart_.selectedNode.value;
      that.querySelector('x-explanation').innerHTML =
          d.value + '<br>' + percent.toFixed(2) + '%';

      // Update call stack table.
      var table = document.createElement('table');
      var thead = table.createTHead();
      var tbody = table.createTBody();
      var headerRow = thead.insertRow(0);
      headerRow.style.backgroundColor = '#888';
      headerRow.insertCell(0).appendChild(
          document.createTextNode('Call Stack'));

      var callStack = [];
      var frame = d;
      while (frame && frame.id) {
        callStack.push(frame);
        frame = frame.parent;
      }

      for (var i = 0; i < callStack.length; i++) {
        var row = tbody.insertRow(i);
        var bgColor = getColorOfKey(callStack[i].category);
        if (bgColor == undefined)
          bgColor = '#444444';
        row.style.backgroundColor = bgColor;
        if (i == 0)
          row.style.fontWeight = 'bold';
        row.insertCell(0).appendChild(
            document.createTextNode(callStack[i].name));
      }

      var sequenceArea = that.querySelector('x-sequence');
      sequenceArea.textContent = '';
      sequenceArea.appendChild(table);
    },

    updateResultArea_: function() {
      var that = this;
      if (that.model_ === undefined)
        return;

      var resultArea = that.querySelector('result-area');
      that.chart_ = undefined;
      resultArea.textContent = '';

      var rangeOfInterest;
      if (that.rangeOfInterest_.isEmpty)
        rangeOfInterest = that.model_.bounds;
      else
        rangeOfInterest = that.rangeOfInterest_;

      var sunburstData =
          createSunburstData(that.model_, rangeOfInterest, that.sampleType_);
      that.chart_ = new tvcm.ui.SunburstChart();
      that.chart_.width = 600;
      that.chart_.height = 600;
      that.chart_.chartTitle = 'Sampling Summary';
      that.chart_.addEventListener('node-selected', function(e) {
        that.updateCallees_(e.node);
      });
      that.chart_.addEventListener('node-highlighted', function(e) {
        that.updateHighlight_(e.node);
      });

      that.chart_.data = {
        nodes: sunburstData
      };

      resultArea.appendChild(that.chart_);
      that.chart_.setSize(that.chart_.getMinSize());
    },

    updateContents_: function() {
      var that = this;
      if (that.model_ === undefined)
        return;

      var rangeOfInterest;
      if (that.rangeOfInterest_.isEmpty)
        rangeOfInterest = that.model_.bounds;
      else
        rangeOfInterest = that.rangeOfInterest_;

      // Get available sample types in range.
      var sampleTypes = getSampleTypes(that.model_, rangeOfInterest);
      if (sampleTypes.indexOf(this.sampleType_) == -1)
        this.sampleType_ = sampleTypes[0];

      // Create sample type dropdown.
      var sampleTypeOptions = [];
      for (var i = 0; i < sampleTypes.length; i++)
        sampleTypeOptions.push({label: sampleTypes[i], value: sampleTypes[i]});

      var toolbarEl = this.querySelector('x-toolbar');
      this.sampleTypeSelector_ = tvcm.ui.createSelector(
          this,
          'sampleType',
          'samplingSummarySidePanel.sampleType',
          this.sampleType_,
          sampleTypeOptions);
      toolbarEl.textContent = 'Sample Type: ';
      toolbarEl.appendChild(this.sampleTypeSelector_);
    }
  };

  tracing.TimelineViewSidePanel.registerPanelSubtype(SamplingSummarySidePanel);

  return {
    SamplingSummarySidePanel: SamplingSummarySidePanel,
    createSunburstData: createSunburstData
  };
});
