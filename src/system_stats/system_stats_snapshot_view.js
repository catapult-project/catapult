// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.requireStylesheet('system_stats.system_stats_snapshot_view');

base.require('tracing.analysis.object_snapshot_view');
base.require('tracing.analysis.util');

base.exportTo('system_stats', function() {
  /*
   * Displays a system stats snapshot in a human readable form. @constructor
   */
  var SystemStatsSnapshotView = ui.define('system-stats-snapshot-view',
      tracing.analysis.ObjectSnapshotView);

  SystemStatsSnapshotView.prototype = {
    __proto__: tracing.analysis.ObjectSnapshotView.prototype,

    decorate: function() {
      this.classList.add('system-stats-snapshot-view');
    },

    updateContents: function() {
      var snapshot = this.objectSnapshot_;
      if (!snapshot || !snapshot.getStats()) {
        this.textContent = 'No system stats snapshot found.';
        return;
      }
      // Clear old snapshot view.
      this.textContent = '';

      var stats = snapshot.getStats();
      this.appendChild(this.buildList_(stats));
    },

    isFloat: function(n) {
      return typeof n === 'number' && n % 1 !== 0;
    },

    /**
     * Creates nested lists.
     *
     * @param {Object} stats The current trace system stats entry.
     * @return {Element} A
     *         <ul>
     *         list element.
     */
    buildList_: function(stats) {
      var statList = document.createElement('ul');

      for (var statName in stats) {
        var statText = document.createElement('li');
        statText.textContent = '' + statName + ': ';
        statList.appendChild(statText);

        if (stats[statName] instanceof Object) {
          statList.appendChild(this.buildList_(stats[statName]));
        } else {
          if (this.isFloat(stats[statName]))
            statText.textContent += stats[statName].toFixed(2);
          else
            statText.textContent += stats[statName];
        }
      }

      return statList;
    }
  };

  tracing.analysis.ObjectSnapshotView.register(
      'base::TraceEventSystemStatsMonitor::SystemStats',
      SystemStatsSnapshotView);

  return {
    SystemStatsSnapshotView: SystemStatsSnapshotView
  };

});
