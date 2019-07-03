/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';

export class AlertsRequest extends RequestBase {
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

  get description_() {
    return 'loading alerts';
  }

  get url_() {
    return AlertsRequest.URL;
  }
}
AlertsRequest.URL = '/api/alerts';

// Maximum number of alerts to fetch from the datastore in a single request.
// AlertsSection.loadAlerts() may chase cursors to load more alerts via
// subsequent requests.
AlertsRequest.PAGE_LIMIT = 500;
