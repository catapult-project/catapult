/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {
  CacheRequestBase, READONLY, READWRITE, jsonResponse,
} from './cache-request-base.js';

const STORE_SIDS = 'sids';

// TODO share with utils.js when vulcanize is replaced with webpack
async function sha(s) {
  s = new TextEncoder('utf-8').encode(s);
  const hash = await crypto.subtle.digest('SHA-256', s);
  const view = new DataView(hash);
  let hex = '';
  for (let i = 0; i < view.byteLength; i += 4) {
    hex += ('00000000' + view.getUint32(i).toString(16)).slice(-8);
  }
  return hex;
}

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

  async maybeValidate_(sid) {
    const isKnown = await this.isKnown_(sid);
    if (isKnown) return;
    const response = await fetch(this.fetchEvent.request);
    const json = await response.json();
    if (json.sid !== sid) {
      throw new Error(`short_uri expected ${sid} actual ${json.sid}`);
    }
  }

  async writeDatabase(sid) {
    const transaction = await this.transaction([STORE_SIDS], READWRITE);
    const store = transaction.objectStore(STORE_SIDS);
    store.put(new Date(), sid);
    await transaction.complete;
  }

  async getResponse() {
    const body = await this.fetchEvent.request.clone().formData();
    const sid = await sha(body.get('page_state'));
    // Update the timestamp even if the sid was already in the database so that
    // we can evict LRU.
    this.scheduleWrite(sid);
    this.fetchEvent.waitUntil(this.maybeValidate_(sid));
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
