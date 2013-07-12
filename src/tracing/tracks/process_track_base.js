// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tcmalloc.heap_instance_track');
base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.object_instance_view');
base.require('tracing.tracks.container_track');
base.require('tracing.tracks.counter_track');
base.require('tracing.tracks.object_instance_track');
base.require('tracing.tracks.spacing_track');
base.require('tracing.tracks.thread_track');
base.require('tracing.trace_model_settings');
base.require('tracing.filter');
base.require('ui');
base.require('ui.dom_helpers');

base.requireStylesheet('tracing.tracks.process_track_base');

base.exportTo('tracing.tracks', function() {

  var ObjectSnapshotView = tracing.analysis.ObjectSnapshotView;
  var ObjectInstanceView = tracing.analysis.ObjectInstanceView;
  var TraceModelSettings = tracing.TraceModelSettings;
  var SpacingTrack = tracing.tracks.SpacingTrack;

  /**
   * Visualizes a Process by building ThreadTracks and CounterTracks.
   * @constructor
   */
  var ProcessTrackBase =
      ui.define('process-track-base', tracing.tracks.ContainerTrack);

  ProcessTrackBase.prototype = {

    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function(viewport) {
      tracing.tracks.ContainerTrack.prototype.decorate.call(this, viewport);

      this.processBase_ = undefined;

      this.classList.add('process-track-base');
      this.classList.add('expanded');

      this.expandEl_ = document.createElement('expand-button');
      this.expandEl_.classList.add('expand-button-expanded');

      this.processNameEl_ = ui.createSpan();

      this.headerEl_ = ui.createDiv({className: 'process-track-header'});
      this.headerEl_.appendChild(this.expandEl_);
      this.headerEl_.appendChild(this.processNameEl_);
      this.headerEl_.addEventListener('click', this.onHeaderClick_.bind(this));

      this.appendChild(this.headerEl_);
    },

    get processBase() {
      return this.processBase_;
    },

    set processBase(processBase) {
      this.processBase_ = processBase;

      if (this.processBase_) {
        var modelSettings = new TraceModelSettings(this.processBase_.model);
        this.expanded = modelSettings.getSettingFor(
            this.processBase_, 'expanded', true);
      }

      this.updateContents_();
    },

    get expanded() {
      return this.expandEl_.classList.contains('expand-button-expanded');
    },

    set expanded(expanded) {
      expanded = !!expanded;

      var wasExpanded = this.expandEl_.classList.contains(
          'expand-button-expanded');
      if (wasExpanded === expanded)
        return;

      if (expanded) {
        this.classList.add('expanded');
        this.expandEl_.classList.add('expand-button-expanded');
      } else {
        this.classList.remove('expanded');
        this.expandEl_.classList.remove('expand-button-expanded');
      }

      // Expanding and collapsing tracks is, essentially, growing and shrinking
      // the viewport. We dispatch a change event to trigger any processing
      // to happen.
      this.viewport_.dispatchChangeEvent();

      if (!this.processBase_)
        return;

      var modelSettings = new TraceModelSettings(this.processBase_.model);
      modelSettings.setSettingFor(this.processBase_, 'expanded', expanded);
    },

    get hasVisibleContent() {
      if (this.expanded)
        return this.children.length > 1;
      return true;
    },

    onHeaderClick_: function(e) {
      e.stopPropagation();
      e.preventDefault();
      this.expanded = !this.expanded;
    },

    updateContents_: function() {
      this.tracks_.forEach(function(track) {
        this.removeChild(track);
      }, this);

      if (!this.processBase_)
        return;

      this.processNameEl_.textContent = this.processBase_.userFriendlyName;
      this.headerEl_.title = this.processBase_.userFriendlyDetails;

      // Create the object instance tracks for this process.
      this.willAppendTracks_();
      this.appendObjectInstanceTracks_();
      this.appendCounterTracks_();
      this.appendThreadTracks_();
      this.didAppendTracks_();
    },

    willAppendTracks_: function() {
    },

    didAppendTracks_: function() {
    },

    appendObjectInstanceTracks_: function() {
      var instancesByTypeName =
          this.processBase_.objects.getAllInstancesByTypeName();
      var instanceTypeNames = base.dictionaryKeys(instancesByTypeName);
      instanceTypeNames.sort();

      var didAppendAtLeastOneTrack = false;
      instanceTypeNames.forEach(function(typeName) {
        var allInstances = instancesByTypeName[typeName];

        // If a object snapshot has a viewer it will be shown,
        // unless the viewer asked for it to not be shown.
        var instanceViewInfo = ObjectInstanceView.getViewInfo(typeName);
        var snapshotViewInfo = ObjectSnapshotView.getViewInfo(typeName);
        if (instanceViewInfo && !instanceViewInfo.options.showInTrackView)
          instanceViewInfo = undefined;
        if (snapshotViewInfo && !snapshotViewInfo.options.showInTrackView)
          snapshotViewInfo = undefined;
        var hasViewInfo = instanceViewInfo || snapshotViewInfo;

        // There are some instances that don't merit their own track in
        // the UI. Filter them out.
        var visibleInstances = [];
        for (var i = 0; i < allInstances.length; i++) {
          var instance = allInstances[i];

          // Do not create tracks for instances that have no snapshots.
          if (instance.snapshots.length === 0)
            continue;

          // Do not create tracks for instances that have implicit snapshots
          // and don't have a viewer.
          if (instance.hasImplicitSnapshots && !hasViewInfo)
            continue;

          visibleInstances.push(instance);
        }
        if (visibleInstances.length === 0)
          return;

        // Look up the constructor for this track, or use the default
        // constructor if none exists.
        var trackConstructor =
            tracing.tracks.ObjectInstanceTrack.getTrackConstructor(typeName);
        if (!trackConstructor)
          trackConstructor = tracing.tracks.ObjectInstanceTrack;
        var track = new trackConstructor(this.viewport);
        track.categoryFilter = this.categoryFilter_;
        track.objectInstances = visibleInstances;
        this.appendChild(track);
        didAppendAtLeastOneTrack = true;
      }, this);
      if (didAppendAtLeastOneTrack)
        this.appendChild(new SpacingTrack(this.viewport));
    },

    appendCounterTracks_: function() {
      // Add counter tracks for this process.
      var counters = base.dictionaryValues(this.processBase.counters).
          filter(this.categoryFilter.matchCounter, this.categoryFilter);
      counters.sort(tracing.trace_model.Counter.compare);

      // Create the counters for this process.
      counters.forEach(function(counter) {
        var track = new tracing.tracks.CounterTrack(this.viewport);
        track.categoryFilter = this.categoryFilter_;
        track.counter = counter;
        this.appendChild(track);
        this.appendChild(new SpacingTrack(this.viewport));
      }.bind(this));
    },

    appendThreadTracks_: function() {
      // Get a sorted list of threads.
      var threads = base.dictionaryValues(this.processBase.threads).
          filter(function(thread) {
            return this.categoryFilter_.matchThread(thread);
          }, this);
      threads.sort(tracing.trace_model.Thread.compare);

      // Create the threads.
      threads.forEach(function(thread) {
        var track = new tracing.tracks.ThreadTrack(this.viewport);
        track.categoryFilter = this.categoryFilter_;
        track.thread = thread;
        if (!track.hasVisibleContent)
          return;
        this.appendChild(track);
        this.appendChild(new SpacingTrack(this.viewport));
      }.bind(this));
    }
  };

  return {
    ProcessTrackBase: ProcessTrackBase
  };
});
