/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ResultChannelReceiver from './result-channel-receiver.js';

export default class RequestBase {
  constructor(options = {}) {
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

  // Some CacheRequest classes use ResultChannelSender to stream parts of the
  // requested data as it becomes available.
  async* reader() {
    // Create the receiver before fetching so we don't miss any results.
    const receiver = new ResultChannelReceiver(this.channelName);
    const response = await this.response;
    if (response) yield response;

    // The service worker doesn't actually run on localhost.
    if (window.IS_DEBUG) return;
    for await (const update of receiver) {
      yield this.postProcess_(update, true);
    }
  }

  get channelName() {
    return (location.origin + this.url_ + '?' +
            new URLSearchParams(this.body_));
  }

  async addAuthorizationHeaders_() {
    if (!window.AUTH_CLIENT_ID) return;
    const headers = await window.getAuthorizationHeaders();
    for (const [name, value] of Object.entries(headers)) {
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

  postProcess_(response, isFromChannel = false) {
    return response;
  }
}
