/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class NewBugRequest extends cp.RequestBase {
    constructor(options) {
      super(options);
      this.method_ = 'POST';
      this.body_ = new FormData();
      for (const key of options.alertKeys) this.body_.append('key', key);
      for (const label of options.labels) this.body_.append('label', label);
      for (const component of options.components) {
        this.body_.append('component', component);
      }
      this.body_.set('summary', options.summary);
      this.body_.set('description', options.description);
      this.body_.set('owner', options.owner);
      this.body_.set('cc', options.cc);
    }

    get url_() {
      return '/api/alerts/new_bug';
    }

    postProcess_(json) {
      return json.bug_id;
    }
  }
  return {NewBugRequest};
});
