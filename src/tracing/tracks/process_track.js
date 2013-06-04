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
base.require('tracing.tracks.thread_track');
base.require('tracing.filter');
base.require('ui');

base.exportTo('tracing.tracks', function() {

  var ObjectSnapshotView = tracing.analysis.ObjectSnapshotView;
  var ObjectInstanceView = tracing.analysis.ObjectInstanceView;

  /**
   * Visualizes a Process by building ThreadTracks and CounterTracks.
   * @constructor
   */
  var ProcessTrack =
      ui.define('process-track', tracing.tracks.ContainerTrack);

  ProcessTrack.prototype = {

    __proto__: tracing.tracks.ContainerTrack.prototype,

    decorate: function() {
      this.classList.add('process-track');
      this.categoryFilter_ = new tracing.Filter();
    },

    get process() {
      return this.process_;
    },

    set process(process) {
      this.process_ = process;
      this.updateChildTracks_();
    },

    applyCategoryFilter_: function() {
      this.visible = (this.categoryFilter.matchProcess(this.process) &&
                      !!this.numVisibleChildTracks);
    },

    updateChildTracks_: function() {
      this.detach();
      if (this.process_) {
        // Create the object instance tracks for this process.
        var instancesByTypeName =
            this.process_.objects.getAllInstancesByTypeName();
        var instanceTypeNames = base.dictionaryKeys(instancesByTypeName);
        instanceTypeNames.sort();
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
          var track = new trackConstructor();
          track.heading = typeName + ':';
          track.objectInstances = visibleInstances;
          this.addTrack_(track);
        }, this);


        // Add counter tracks for this process.
        var counters = [];
        for (var tid in this.process.counters) {
          counters.push(this.process.counters[tid]);
        }
        counters.sort(tracing.trace_model.Counter.compare);

        // Create the counters for this process.
        counters.forEach(function(counter) {
          var track = new tracing.tracks.CounterTrack();
          track.heading = counter.name + ':';
          track.counter = counter;
          this.addTrack_(track);
        }.bind(this));

        // Get a sorted list of threads.
        var threads = [];
        for (var tid in this.process.threads)
          threads.push(this.process.threads[tid]);
        threads.sort(tracing.trace_model.Thread.compare);

        // Create the threads.
        threads.forEach(function(thread) {
          var track = new tracing.tracks.ThreadTrack();
          track.heading = thread.userFriendlyName + ':';
          track.tooltip = thread.userFriendlyDetails;
          track.thread = thread;
          this.addTrack_(track);
        }.bind(this));
      }
    }
  };

  return {
    ProcessTrack: ProcessTrack
  };
});
