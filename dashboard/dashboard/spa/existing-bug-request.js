/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import RequestBase from './request-base.js';

export default class ExistingBugRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.method_ = 'POST';
    this.body_ = new FormData();
    for (const key of options.alertKeys) this.body_.append('key', key);
    this.body_.set('bug', options.bugId);
  }

  get url_() {
    return ExistingBugRequest.URL;
  }
}
ExistingBugRequest.URL = '/api/existing_bug';
