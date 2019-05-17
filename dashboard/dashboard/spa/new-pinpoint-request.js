/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import RequestBase from './request-base.js';

export default class NewPinpointRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.method_ = 'POST';
    this.body_ = new FormData();
    this.body_.set('alerts', JSON.stringify(options.alerts));
    this.body_.set('suite', options.suite);
    this.body_.set('bot', options.bot);
    this.body_.set('measurement', options.measurement);
    this.body_.set('case', options.case);
    this.body_.set('statistic', options.statistic);
    this.body_.set('bisect_mode', options.mode);
    this.body_.set('bug_id', options.bugId);
    this.body_.set('pin', options.patch);
    this.body_.set('start_commit', options.startRevision);
    this.body_.set('end_commit', options.endRevision);
  }

  get url_() {
    return NewPinpointRequest.URL;
  }

  get description_() {
    return 'starting pinpoint job';
  }

  postProcess_(response, isFromChannel = false) {
    if (!response) throw new Error('empty response');
    if (!response.jobId || response.error) throw new Error(response.error);
    return response.jobId;
  }
}
NewPinpointRequest.URL = '/api/new_pinpoint';
