/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {RequestBase} from './request-base.js';

export class SheriffsRequest extends RequestBase {
  constructor(options = {}) {
    super(options);
    this.method_ = 'POST';
  }

  get url_() {
    return SheriffsRequest.URL;
  }

  get description_() {
    return 'loading sheriffs';
  }
}
SheriffsRequest.URL = '/api/sheriffs';
