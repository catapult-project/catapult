/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {CacheRequestBase, READONLY, READWRITE} from './cache-request-base.js';

const STORE_DATA = 'data';
const EXPIRATION_MS = 20 * 60 * 60 * 1000;

export default class KeyValueCacheRequest extends CacheRequestBase {
  get isAuthorized() {
    return this.fetchEvent.request.headers.has('Authorization');
  }

  get databaseKeyPromise() {
    if (!this.databaseKeyPromise_) {
      this.databaseKeyPromise_ = this.getDatabaseKey();
    }
    return this.databaseKeyPromise_;
  }

  get databaseName() {
    return 'keyvalue';
  }

  get databaseVersion() {
    return 1;
  }

  async upgradeDatabase(db) {
    if (db.oldVersion < 1) {
      db.createObjectStore(STORE_DATA);
    }
  }

  async getDatabaseKey() {
    throw new Error(`${this.constructor.name} must override getDatabaseKey`);
  }

  async writeDatabase({key, value}) {
    const db = await this.databasePromise;
    const transaction = db.transaction([STORE_DATA], READWRITE);
    const dataStore = transaction.objectStore(STORE_DATA);
    const expiration = new Date(new Date().getTime() + EXPIRATION_MS);
    dataStore.put({value, expiration: expiration.toISOString()}, key);
    await transaction.complete;
  }

  async readDatabase_(key) {
    const db = await this.databasePromise;
    const transaction = db.transaction([STORE_DATA], READONLY);
    const dataStore = transaction.objectStore(STORE_DATA);
    return await dataStore.get(key);
  }

  async getResponse() {
    const key = await this.databaseKeyPromise;
    const otherRequest = await this.findInProgressRequest(async other =>
      ((await other.databaseKeyPromise) === key));
    if (otherRequest) {
      // Be sure to call onComplete() to remove `this` from IN_PROGRESS_REQUESTS
      // so that `otherRequest.getResponse()` doesn't await
      // `this.getResponse()`, which would cause both of these requests to
      // deadlock.
      this.onComplete();
      return await otherRequest.responsePromise;
    }

    const entry = await this.readDatabase_(key);
    if (entry && (new Date(entry.expiration) > new Date())) {
      return entry.value;
    }

    const response = await fetch(this.fetchEvent.request);
    const value = await response.json();
    this.scheduleWrite({key, value});
    return value;
  }
}
