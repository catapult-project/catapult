/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class SessionStateRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.sessionId_ = options.sessionId;
    }

    get url_() {
      return `/short_uri?v2=true&sid=${this.sessionId_}`;
    }
  }

  return {SessionStateRequest};
});
