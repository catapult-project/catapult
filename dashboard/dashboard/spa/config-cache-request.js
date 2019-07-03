/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {KeyValueCacheRequest} from './key-value-cache-request.js';

export class ConfigCacheRequest extends KeyValueCacheRequest {
  async getDatabaseKey() {
    const body = await this.fetchEvent.request.clone().formData();
    const key = body.get('key');
    return `config_${key}_${this.isAuthorized ? '_internal' : ''}`;
  }
}
