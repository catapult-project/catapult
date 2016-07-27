// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * This view displays a summary of the state of each SPDY sessions, and
 * has links to display them in the events tab.
 */
var SpdyView = (function() {
  'use strict';

  // We inherit from DivView.
  var superClass = DivView;

  /**
   * @constructor
   */
  function SpdyView() {
    assertFirstConstructorCall(SpdyView);

    // Call superclass's constructor.
    superClass.call(this, SpdyView.MAIN_BOX_ID);

    g_browser.addSpdySessionInfoObserver(this, true);
    g_browser.addSpdyStatusObserver(this, true);
  }

  SpdyView.TAB_ID = 'tab-handle-spdy';
  SpdyView.TAB_NAME = 'HTTP/2';
  SpdyView.TAB_HASH = '#http2';

  // IDs for special HTML elements in spdy_view.html
  SpdyView.MAIN_BOX_ID = 'spdy-view-tab-content';
  SpdyView.STATUS_ID = 'spdy-view-status';
  SpdyView.STATUS_HTTP2_ENABLED = 'spdy-view-http2-enabled';
  SpdyView.STATUS_SPDY31_ENABLED = 'spdy-view-spdy31-enabled';
  SpdyView.STATUS_ALTERNATE_SERVICE = 'spdy-view-alternate-service';
  SpdyView.STATUS_ALPN_PROTOCOLS = 'spdy-view-alpn-protocols';
  SpdyView.STATUS_NPN_PROTOCOLS = 'spdy-view-npn-protocols';
  SpdyView.SESSION_INFO_ID = 'spdy-view-session-info';
  SpdyView.SESSION_INFO_CONTENT_ID = 'spdy-view-session-info-content';
  SpdyView.SESSION_INFO_NO_CONTENT_ID =
      'spdy-view-session-info-no-content';
  SpdyView.SESSION_INFO_TBODY_ID = 'spdy-view-session-info-tbody';

  cr.addSingletonGetter(SpdyView);

  SpdyView.prototype = {
    // Inherit the superclass's methods.
    __proto__: superClass.prototype,

    onLoadLogFinish: function(data) {
      return this.onSpdySessionInfoChanged(data.spdySessionInfo) &&
             this.onSpdyStatusChanged(data.spdyStatus);
    },

    /**
     * If |spdySessionInfo| contains any sessions, displays a single table with
     * information on each SPDY session.  Otherwise, displays "None".
     */
    onSpdySessionInfoChanged: function(spdySessionInfo) {
      if (!spdySessionInfo)
        return false;

      var hasSpdySessionInfo = spdySessionInfo && spdySessionInfo.length > 0;

      setNodeDisplay($(SpdyView.SESSION_INFO_CONTENT_ID), hasSpdySessionInfo);
      setNodeDisplay($(SpdyView.SESSION_INFO_NO_CONTENT_ID),
          !hasSpdySessionInfo);

      var tbody = $(SpdyView.SESSION_INFO_TBODY_ID);
      tbody.innerHTML = '';

      // Fill in the sessions info table.
      for (var i = 0; i < spdySessionInfo.length; ++i) {
        var s = spdySessionInfo[i];
        var tr = addNode(tbody, 'tr');

        var hostCell = addNode(tr, 'td');
        addNodeWithText(hostCell, 'span', s.host_port_pair);
        addNodeWithText(hostCell, 'span',
            s.aliases ? ' ' + s.aliases.join(' ') : '');

        addNodeWithText(tr, 'td', s.proxy);

        var idCell = addNode(tr, 'td');
        var a = addNodeWithText(idCell, 'a', s.source_id);
        a.href = '#events&q=id:' + s.source_id;

        var kFields = ['protocol_negotiated', 'active_streams',
          'unclaimed_pushed_streams', 'max_concurrent_streams',
          'streams_initiated_count', 'streams_pushed_count',
          'streams_pushed_and_claimed_count',
          'streams_abandoned_count', 'frames_received', 'is_secure',
          'sent_settings', 'received_settings', 'send_window_size',
          'recv_window_size', 'unacked_recv_window_bytes', 'error'];

        for (var fieldIndex = 0; fieldIndex < kFields.length; ++fieldIndex) {
          addNodeWithText(tr, 'td', s[kFields[fieldIndex]]);
        }
      }

      return true;
    },

    /**
     * Displays information on the global SPDY status.
     */
    onSpdyStatusChanged: function(spdyStatus) {
      if (!spdyStatus)
        return false;

      $(SpdyView.STATUS_HTTP2_ENABLED).textContent =
          (spdyStatus.enable_http2 == undefined ?
           spdyStatus.spdy_enabled : spdyStatus.enable_http2);

      $(SpdyView.STATUS_SPDY31_ENABLED).textContent =
          (spdyStatus.enable_spdy31 == undefined ?
           spdyStatus.spdy_enabled : spdyStatus.enable_spdy31);

      $(SpdyView.STATUS_ALTERNATE_SERVICE).textContent =
          (spdyStatus.use_alternative_services == undefined ?
           spdyStatus.use_alternate_protocols :
           spdyStatus.use_alternative_services);

      $(SpdyView.STATUS_ALPN_PROTOCOLS).textContent =
          (spdyStatus.alpn_protos || spdyStatus.next_protos);

      $(SpdyView.STATUS_NPN_PROTOCOLS).textContent =
          (spdyStatus.npn_protos || spdyStatus.next_protos);

      return true;
    }
  };

  return SpdyView;
})();

