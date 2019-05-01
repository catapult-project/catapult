/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class ResultChannelReceiver {
  constructor(url) {
    this.messageQueue_ = [];
    this.onMessage_ = undefined;
    this.handleMessage_ = this.handleMessage_.bind(this);
    this.channel_ = new BroadcastChannel(url);
    this.channel_.addEventListener('message', this.handleMessage_);
  }

  handleMessage_({data}) {
    this.messageQueue_.push(data);
    if (this.onMessage_) this.onMessage_();
  }

  async next() {
    if (this.messageQueue_.length === 0) {
      await new Promise(resolve => {
        this.onMessage_ = resolve;
      });
      this.onMessage_ = undefined;
    }
    const {type, payload} = this.messageQueue_.shift();
    switch (type) {
      case 'RESULT':
        return {done: false, value: payload};

      case 'ERROR':
        throw new Error(payload);

      case 'DONE':
        this.channel_.removeEventListener('message', this.handleMessage_);
        this.channel_.close();
        return {done: true};

      default:
        throw new Error(`Unknown message type: ${type}`);
    }
  }

  [Symbol.asyncIterator]() {
    return this;
  }
}
