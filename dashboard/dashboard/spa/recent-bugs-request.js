/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class RecentBugsRequest extends cp.RequestBase {
  constructor() {
    super({});
    this.method_ = 'POST';
  }

  get url_() {
    return RecentBugsRequest.URL;
  }

  postProcess_(json) {
    return json.bugs;
  }
}
RecentBugsRequest.URL = '/api/bugs/recent';
