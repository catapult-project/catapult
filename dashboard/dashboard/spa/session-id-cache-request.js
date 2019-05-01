/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import ResultChannelSender from './result-channel-sender.js';
import {
  CacheRequestBase, READONLY, READWRITE, jsonResponse,
} from './cache-request-base.js';

import sha from './sha.js';

const STORE_SIDS = 'sids';

export default class SessionIdCacheRequest extends CacheRequestBase {
  get timingCategory() {
    return 'short_uri';
  }

  get databaseName() {
    return 'short_uri';
  }

  get databaseVersion() {
    return 1;
  }

  async upgradeDatabase(db) {
    if (db.oldVersion < 1) {
      db.createObjectStore(STORE_SIDS);
    }
  }

  async isKnown_(sid) {
    const other = await this.findInProgressRequest(async other => {
      const otherResponse = await other.responsePromise;
      return otherResponse.sid === sid;
    });
    if (other) return true;
    const transaction = await this.transaction([STORE_SIDS], READONLY);
    const store = transaction.objectStore(STORE_SIDS);
    const entry = await store.get(sid);
    return entry !== undefined;
  }

  maybeValidate_(sid) {
    return (async function* () {
      const isKnown = await this.isKnown_(sid);
      if (isKnown) return;
      const response = await fetch(this.fetchEvent.request);
      const json = await response.json();
      if (json.sid !== sid) {
        throw new Error(`short_uri expected ${sid} actual ${json.sid}`);
      }
    }).call(this);
  }

  async writeDatabase(sid) {
    const transaction = await this.transaction([STORE_SIDS], READWRITE);
    const store = transaction.objectStore(STORE_SIDS);
    store.put(new Date(), sid);
    await transaction.complete;
  }

  async getResponse() {
    const body = await this.fetchEvent.request.clone().formData();
    const pageState = body.get('page_state');
    const sid = await sha(pageState);
    // Update the timestamp even if the sid was already in the database so that
    // we can evict LRU.
    this.scheduleWrite(sid);
    const sender = new ResultChannelSender(this.fetchEvent.request.url + '?' +
      new URLSearchParams({page_state: pageState}));
    this.fetchEvent.waitUntil(sender.send(this.maybeValidate_(sid)));
    return {sid};
  }

  async respond() {
    // Allow the browser to handle GET /short_uri?sid requests.
    if (this.fetchEvent.request.method !== 'POST') {
      // Normally, super.respond() or scheduleWrite() would call onComplete(),
      // but we're skipping those so we must call onComplete here.
      this.onComplete();
      return;
    }

    await super.respond();
  }
}
