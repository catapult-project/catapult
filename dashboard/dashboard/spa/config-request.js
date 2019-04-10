/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ConfigRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.method_ = 'POST';
      this.body_ = new FormData();
      this.body_.set('key', options.key);
    }

    get url_() {
      return ConfigRequest.URL;
    }
  }
  ConfigRequest.URL = '/api/config';
  return {ConfigRequest};
});
