/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';
import {plural} from './utils.js';

export class NudgeAlertRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.method_ = 'POST';
    this.body_ = new FormData();
    for (const key of options.alertKeys) this.body_.append('key', key);
    this.body_.set('new_start_revision', options.startRevision);
    this.body_.set('new_end_revision', options.endRevision);
  }

  get url_() {
    return NudgeAlertRequest.URL;
  }

  get description_() {
    const count = this.body_.getAll('key').length;
    return `nudging ${count} alert${plural(count)} to
      ${this.body_.get('new_end_revision')}`;
  }

  postProcess_(response, isFromChannel = false) {
    if (!response) throw new Error('null response');
    if (response.error) throw new Error(response.error);
    return response;
  }
}
NudgeAlertRequest.URL = '/api/nudge_alert';
