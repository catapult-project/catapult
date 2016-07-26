// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * This view displays a summary of the state of each QUIC session, and
 * has links to display them in the events tab.
 */
var QuicView = (function() {
  'use strict';

  // We inherit from DivView.
  var superClass = DivView;

  /**
   * @constructor
   */
  function QuicView() {
    assertFirstConstructorCall(QuicView);

    // Call superclass's constructor.
    superClass.call(this, QuicView.MAIN_BOX_ID);

    g_browser.addQuicInfoObserver(this, true);
  }

  QuicView.TAB_ID = 'tab-handle-quic';
  QuicView.TAB_NAME = 'QUIC';
  QuicView.TAB_HASH = '#quic';

  // IDs for special HTML elements in quic_view.html
  QuicView.MAIN_BOX_ID = 'quic-view-tab-content';
  QuicView.STATUS_QUIC_ENABLED = 'quic-view-quic-enabled';
  QuicView.STATUS_ORIGINS_TO_FORCE_QUIC_ON =
      'quic-view-origins-to-force-quic-on';
  QuicView.STATUS_CONNECTION_OPTIONS =
      'quic-view-connection-options';
  QuicView.STATUS_CONSISTENT_PORT_SELECTION_ENABLED =
      'quic-view-port-selection-enabled';
  QuicView.STATUS_LOAD_SERVER_INFO_TIMEOUT_MULTIPLIER =
      'quic-view-server-info-timeout-mult';
  QuicView.STATUS_ENABLE_CONNECTION_RACING =
      'quic-view-enable-connection-racing';
  QuicView.STATUS_DISABLE_DISK_CACHE =
      'quic-view-disable-disk-cache';
  QuicView.STATUS_PREFER_AES =
      'quic-view-prefer-aes';
  QuicView.STATUS_MAX_NUM_OF_LOSSY_CONNECTIONS =
      'quic-view-max-num-lossy-connections';
  QuicView.STATUS_PACKET_LOSS_THRESHOLD =
      'quic-view-packet-loss-threshold';
  QuicView.STATUS_DELAY_TCP_RACE = 'quic-view-delay-tcp-race';
  QuicView.STATUS_STORE_SERVER_CONFIGS_IN_PROPERITES_FILE =
      'quic-view-configs-in-file';
  QuicView.STATUS_IDLE_CONNECTION_TIMEOUT_IN_SECS =
      'quic-view-connection-timeout-in-secs';
  QuicView.STATUS_DISABLE_PRECONNECT_IF_ORTT =
      'quic-view-disable-preconnect-if-ortt';
  QuicView.STATUS_DISABLE_QUIC_ON_TIMEOUT_WITH_OPEN_STREAMS =
      'quic-view-disable-quic-on-timeout-with-open-streams';
  QuicView.STATUS_DYNAMICALLY_DISABLED_BULLET_POINT =
      'quic-view-dynamically-disabled-bullet-point';
  QuicView.STATUS_DYNAMICALLY_DISABLED_SPAN =
      'quic-view-dynamically-disabled-span';
  QuicView.SESSION_INFO_CONTENT_ID =
      'quic-view-session-info-content';
  QuicView.SESSION_INFO_NO_CONTENT_ID =
      'quic-view-session-info-no-content';
  QuicView.SESSION_INFO_TBODY_ID = 'quic-view-session-info-tbody';

  cr.addSingletonGetter(QuicView);

  QuicView.prototype = {
    // Inherit the superclass's methods.
    __proto__: superClass.prototype,

    onLoadLogFinish: function(data) {
      return this.onQuicInfoChanged(data.quicInfo);
    },

    /**
     * If there are any sessions, display a single table with
     * information on each QUIC session.  Otherwise, displays "None".
     */
    onQuicInfoChanged: function(quicInfo) {
      if (!quicInfo)
        return false;

      $(QuicView.STATUS_QUIC_ENABLED).textContent =
          !!quicInfo.quic_enabled;

      $(QuicView.STATUS_ORIGINS_TO_FORCE_QUIC_ON).textContent =
          quicInfo.origins_to_force_quic_on;

      $(QuicView.STATUS_CONNECTION_OPTIONS).textContent =
          quicInfo.connection_options;

      $(QuicView.STATUS_CONSISTENT_PORT_SELECTION_ENABLED).
          textContent = !!quicInfo.enable_quic_port_selection;

      $(QuicView.STATUS_LOAD_SERVER_INFO_TIMEOUT_MULTIPLIER).
          textContent = quicInfo.load_server_info_timeout_srtt_multiplier;

      $(QuicView.STATUS_ENABLE_CONNECTION_RACING).textContent =
          !!quicInfo.enable_connection_racing;

      $(QuicView.STATUS_DISABLE_DISK_CACHE).textContent =
          !!quicInfo.disable_disk_cache;

      $(QuicView.STATUS_PREFER_AES).textContent =
          !!quicInfo.prefer_aes;

      $(QuicView.STATUS_MAX_NUM_OF_LOSSY_CONNECTIONS).textContent =
          quicInfo.max_number_of_lossy_connections;

      $(QuicView.STATUS_PACKET_LOSS_THRESHOLD).textContent =
          quicInfo.packet_loss_threshold;

      $(QuicView.STATUS_DELAY_TCP_RACE).textContent =
          !!quicInfo.delay_tcp_race;

      $(QuicView.STATUS_STORE_SERVER_CONFIGS_IN_PROPERITES_FILE).
          textContent = !!quicInfo.store_server_configs_in_properties;

      $(QuicView.STATUS_IDLE_CONNECTION_TIMEOUT_IN_SECS).textContent =
          quicInfo.idle_connection_timeout_seconds;

      $(QuicView.STATUS_DISABLE_PRECONNECT_IF_ORTT).textContent =
          quicInfo.disable_preconnect_if_0rtt;

      $(QuicView.STATUS_DISABLE_QUIC_ON_TIMEOUT_WITH_OPEN_STREAMS).
          textContent =
              quicInfo.disable_quic_on_timeout_with_open_streams;

      setNodeDisplay($(QuicView.STATUS_DYNAMICALLY_DISABLED_BULLET_POINT),
          quicInfo.disabled_reason && quicInfo.disabled_reason.length > 0);
      if (quicInfo.disabled_reason &&
          quicInfo.disabled_reason.length > 0) {
        $(QuicView.STATUS_DYNAMICALLY_DISABLED_SPAN).textContent =
            'QUIC dynamically disabled: ' + quicInfo.disabled_reason;
      }

      var sessions = quicInfo.sessions;

      var hasSessions = sessions && sessions.length > 0;

      setNodeDisplay($(QuicView.SESSION_INFO_CONTENT_ID), hasSessions);
      setNodeDisplay($(QuicView.SESSION_INFO_NO_CONTENT_ID), !hasSessions);

      var tbody = $(QuicView.SESSION_INFO_TBODY_ID);
      tbody.innerHTML = '';

      // Fill in the sessions info table.
      for (var i = 0; i < sessions.length; ++i) {
        var q = sessions[i];
        var tr = addNode(tbody, 'tr');

        addNodeWithText(tr, 'td', q.aliases ? q.aliases.join(' ') : '');
        addNodeWithText(tr, 'td', !!q.secure);
        addNodeWithText(tr, 'td', q.version);
        addNodeWithText(tr, 'td', q.peer_address);

        var connectionUIDCell = addNode(tr, 'td');
        var a = addNode(connectionUIDCell, 'a');
        a.href = '#events&q=type:QUIC_SESSION%20' + q.connection_id;
        a.textContent = q.connection_id;

        addNodeWithText(tr, 'td', q.open_streams);

        addNodeWithText(tr, 'td',
            q.active_streams && q.active_streams.length > 0 ?
            q.active_streams.join(', ') : 'None');

        addNodeWithText(tr, 'td', q.total_streams);
        addNodeWithText(tr, 'td', q.packets_sent);
        addNodeWithText(tr, 'td', q.packets_lost);
        addNodeWithText(tr, 'td', q.packets_received);
        addNodeWithText(tr, 'td', q.connected);
      }

      return true;
    },
  };

  return QuicView;
})();

