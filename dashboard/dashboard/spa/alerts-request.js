/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class AlertsRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.method_ = 'POST';
      this.body_ = new FormData();
      this.body_.set('v2', '1');
      this.body_.set('limit', AlertsRequest.PAGE_LIMIT);
      for (const [key, value] of Object.entries(options.body)) {
        this.body_.set(key, value);
      }
    }

    get url_() {
      return AlertsRequest.URL;
    }
  }
  AlertsRequest.URL = '/api/alerts';

  // Maximum number of alerts to fetch from the datastore in a single request.
  // AlertsSection.actions.loadAlerts may chase cursors to load more alerts via
  // subsequent requests.
  AlertsRequest.PAGE_LIMIT = 500;

  return {AlertsRequest};
});
