/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class ReportNamesRequest extends cp.RequestBase {
  constructor(options = {}) {
    super(options);
    this.method_ = 'POST';
  }

  get url_() {
    return ReportNamesRequest.URL;
  }

  postProcess_(json) {
    return json.map(info => {
      return {...info, modified: new Date(info.modified)};
    });
  }
}
ReportNamesRequest.URL = '/api/report/names';
