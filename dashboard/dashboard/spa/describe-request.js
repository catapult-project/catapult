/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class DescribeRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.method_ = 'POST';
      this.body_ = new FormData();
      this.body_.set('test_suite', options.testSuite);
    }

    get url_() {
      return DescribeRequest.URL;
    }

    static mergeDescriptor(merged, descriptor) {
      for (const bot of descriptor.bots) merged.bots.add(bot);
      for (const measurement of descriptor.measurements) {
        merged.measurements.add(measurement);
      }
      for (const c of descriptor.cases) {
        merged.cases.add(c);
      }
      for (const [tag, cases] of Object.entries(descriptor.caseTags || {})) {
        if (!merged.caseTags.has(tag)) {
          merged.caseTags.set(tag, new Set());
        }
        for (const c of cases) {
          merged.caseTags.get(tag).add(c);
        }
      }
    }
  }
  DescribeRequest.URL = '/api/describe';
  return {DescribeRequest};
});
