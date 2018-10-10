/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

export default class ResultChannelSender {
  constructor(url) {
    this.channel_ = new BroadcastChannel(url);
  }

  async send(asyncGenerator) {
    for await (const payload of asyncGenerator) {
      this.channel_.postMessage({type: 'RESULT', payload});
    }
    this.channel_.postMessage({type: 'DONE'});
    this.channel_.close();
  }
}
