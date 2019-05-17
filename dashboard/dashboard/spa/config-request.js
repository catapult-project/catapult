/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import RequestBase from './request-base.js';

export default class ConfigRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.method_ = 'POST';
    this.body_ = new FormData();
    this.body_.set('key', options.key);
  }

  get url_() {
    return ConfigRequest.URL;
  }

  get description_() {
    return `loading ${this.body_.get('key')}`;
  }
}
ConfigRequest.URL = '/api/config';
