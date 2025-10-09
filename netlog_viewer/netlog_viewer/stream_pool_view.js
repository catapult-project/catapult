// Copyright 2025 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * This view displays information on the state of the HTTP stream pool.
 *
 *   - Shows a summary of the HTTP stream pool state at the top.
 *   - Shows a table of all groups with their stream counts.
 *   - Shows detailed attempt state for groups with active attempt managers.
 */
const StreamPoolView = (function() {
  // We inherit from DivView.
  const superClass = DivView;

  /**
   * @constructor
   */
  function StreamPoolView() {
    assertFirstConstructorCall(StreamPoolView);

    // Call superclass's constructor.
    superClass.call(this, StreamPoolView.MAIN_BOX_ID);

    g_browser.addHttpStreamPoolInfoObserver(this, true);
    this.summaryDiv_ = $(StreamPoolView.SUMMARY_DIV_ID);
    this.groupsDiv_ = $(StreamPoolView.GROUPS_DIV_ID);
    this.attemptStateDiv_ = $(StreamPoolView.ATTEMPT_STATE_DIV_ID);
  }

  StreamPoolView.TAB_ID = 'tab-handle-stream-pool';
  StreamPoolView.TAB_NAME = 'StreamPool';
  StreamPoolView.TAB_HASH = '#streamPool';

  // IDs for special HTML elements in stream_pool_view.html
  StreamPoolView.MAIN_BOX_ID = 'stream-pool-view-tab-content';
  StreamPoolView.SUMMARY_DIV_ID = 'stream-pool-view-summary-div';
  StreamPoolView.GROUPS_DIV_ID = 'stream-pool-view-groups-div';
  StreamPoolView.ATTEMPT_STATE_DIV_ID = 'stream-pool-view-attempt-state-div';

  cr.addSingletonGetter(StreamPoolView);

  StreamPoolView.prototype = {
    // Inherit the superclass's methods.
    __proto__: superClass.prototype,

    onLoadLogFinish: function(data) {
      return this.onHttpStreamPoolInfoChanged(data.httpStreamPoolInfo);
    },

    onHttpStreamPoolInfoChanged: function(httpStreamPoolInfo) {
      this.summaryDiv_.innerHTML = '';
      this.groupsDiv_.innerHTML = '';
      this.attemptStateDiv_.innerHTML = '';

      if (!httpStreamPoolInfo) {
        return false;
      }

      // Create and display summary table.
      const summaryTablePrinter = this.createSummaryTablePrinter_(
          httpStreamPoolInfo);
      summaryTablePrinter.toHTML(this.summaryDiv_, 'styled-table');

      // Create and display groups table.
      const groupsTablePrinter = this.createGroupsTablePrinter_(
          httpStreamPoolInfo);
      groupsTablePrinter.toHTML(this.groupsDiv_, 'styled-table');

      // Create and display attempt state details.
      this.createAttemptStateHTML_(httpStreamPoolInfo);

      return true;
    },

    /**
     * Creates a table printer containing summary information about
     * the HTTP stream pool.
     */
    createSummaryTablePrinter_: function(httpStreamPoolInfo) {
      const tablePrinter = new TablePrinter();
      tablePrinter.addHeaderCell('Property');
      tablePrinter.addHeaderCell('Value');

      tablePrinter.addRow();
      tablePrinter.addCell('Connecting Socket Count');
      tablePrinter.addCell(httpStreamPoolInfo.connecting_socket_count);

      tablePrinter.addRow();
      tablePrinter.addCell('Handed Out Socket Count');
      tablePrinter.addCell(httpStreamPoolInfo.handed_out_socket_count);

      tablePrinter.addRow();
      tablePrinter.addCell('Idle Socket Count');
      tablePrinter.addCell(httpStreamPoolInfo.idle_socket_count);

      tablePrinter.addRow();
      tablePrinter.addCell('Max Socket Count');
      tablePrinter.addCell(httpStreamPoolInfo.max_socket_count);

      tablePrinter.addRow();
      tablePrinter.addCell('Max Sockets Per Group');
      tablePrinter.addCell(httpStreamPoolInfo.max_sockets_per_group);

      let groupCount = 0;
      if (httpStreamPoolInfo.groups) {
        groupCount = Object.keys(httpStreamPoolInfo.groups).length;
      }
      tablePrinter.addRow();
      tablePrinter.addCell('Groups Count');
      tablePrinter.addCell(groupCount);

      let jobCount = 0;
      if (httpStreamPoolInfo.job_controllers) {
        jobCount = httpStreamPoolInfo.job_controllers.length;
      }
      tablePrinter.addRow();
      tablePrinter.addCell('Active Job Controllers');
      tablePrinter.addCell(jobCount);

      return tablePrinter;
    },

    /**
     * Creates a table printer containing information on all stream pool groups.
     */
    createGroupsTablePrinter_: function(httpStreamPoolInfo) {
      const tablePrinter = new TablePrinter();
      tablePrinter.setTitle('HTTP Stream Pool Groups');

      tablePrinter.addHeaderCell('Group Name');
      tablePrinter.addHeaderCell('Active');
      tablePrinter.addHeaderCell('Handed Out');
      tablePrinter.addHeaderCell('Idle');
      tablePrinter.addHeaderCell('Attempt Manager');

      if (!httpStreamPoolInfo.groups) {
        return tablePrinter;
      }

      for (const groupName in httpStreamPoolInfo.groups) {
        const group = httpStreamPoolInfo.groups[groupName];

        tablePrinter.addRow();
        tablePrinter.addCell(groupName);
        tablePrinter.addCell(group.active_socket_count || 0);
        tablePrinter.addCell(group.handed_out_socket_count || 0);
        tablePrinter.addCell(group.idle_socket_count || 0);
        tablePrinter.addCell(group.attempt_manager_alive ? 'alive' : '-');
      }

      return tablePrinter;
    },

    /**
     * Creates HTML content for detailed attempt state information.
     */
    // TODO(bashi): Don't rely on JSON.stringify for formatting. Make it
    // prettier.
    createAttemptStateHTML_: function(httpStreamPoolInfo) {
      if (!httpStreamPoolInfo.groups) {
        return;
      }

      let html = '';
      for (let groupName in httpStreamPoolInfo.groups) {
        const group = httpStreamPoolInfo.groups[groupName];

        if (group.attempt_manager_alive && group.attempt_state) {
          html += '<div style="margin-top: 20px; padding: 10px; ' +
              'border: 1px solid #ccc;">';
          html += '<h4>Attempt State for: ' + escapeHTML(groupName) +
              '</h4>';
          html += '<pre>' +
              escapeHTML(JSON.stringify(group.attempt_state, null, 2)) +
              '</pre>';
          html += '</div>';
        }
      }

      if (html) {
        this.attemptStateDiv_.innerHTML = html;
      }
    }
  };

  /**
   * Escapes HTML special characters.
   */
  function escapeHTML(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  return StreamPoolView;
})();
