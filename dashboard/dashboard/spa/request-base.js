/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class RequestBase {
    constructor(options) {
      this.responsePromise_ = undefined;
      this.method_ = 'GET';
      this.headers_ = new Headers(options.headers);
      this.body_ = undefined;
    }

    get url_() {
      throw new Error('subclasses must override get url_()');
    }

    get response() {
      // Don't call fetch_ before the subclass constructor finishes.
      if (!this.responsePromise_) this.responsePromise_ = this.fetch_();
      return this.responsePromise_;
    }

    async addAuthorizationHeaders_() {
      if (!window.getAuthorizationHeaders) return;
      const headers = await window.getAuthorizationHeaders();
      for (const [name, value] of headers) {
        this.headers_.set(name, value);
      }
    }

    async fetch_() {
      await this.addAuthorizationHeaders_();
      const mark = tr.b.Timing.mark('fetch', this.constructor.name);
      const response = await fetch(this.url_, {
        body: this.body_,
        headers: this.headers_,
        method: this.method_,
      });
      mark.end();
      return this.postProcess_(await response.json());
    }

    postProcess_(response) {
      return response;
    }
  }

  return {RequestBase};
});
