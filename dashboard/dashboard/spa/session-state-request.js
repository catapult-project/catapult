/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';

export class SessionStateRequest extends RequestBase {
  constructor(options) {
    super(options);
    this.sessionId_ = options.sessionId;
  }

  get url_() {
    return `${SessionStateRequest.URL}?v2=true&sid=${this.sessionId_}`;
  }

  get description_() {
    return 'loading session state';
  }
}
SessionStateRequest.URL = '/short_uri';
