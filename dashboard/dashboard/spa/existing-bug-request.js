/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';

export class ExistingBugRequest extends RequestBase {
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

  get description_() {
    return `assigning ${this.body_.getAll('key').length} alerts to
      ${this.body_.get('bug')}`;
  }
}
ExistingBugRequest.IGNORE_BUG_ID = -2;
ExistingBugRequest.URL = '/api/existing_bug';
