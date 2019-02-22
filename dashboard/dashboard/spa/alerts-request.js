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
      for (const [key, value] of Object.entries(options.body)) {
        this.body_.set(key, value);
      }
    }

    get url_() {
      return AlertsRequest.URL;
    }
  }
  AlertsRequest.URL = '/api/alerts';
  return {AlertsRequest};
});
