/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './chops-signin-aware.js';
import {afterRender} from './utils.js';
import {assert} from 'chai';

suite('chops-signin-aware', function() {
  let origGetUserProfile;
  let origGetAuthorizationHeaders;
  setup(() => {
    origGetUserProfile = window.getUserProfileSync;
    origGetAuthorizationHeaders = window.getAuthorizationHeaders;
    window.getUserProfileSync = () => undefined;
    window.getAuthorizationHeaders = async() => undefined;
  });

  teardown(() => {
    window.getUserProfileSync = origGetUserProfile;
    for (const child of document.body.children) {
      if (!child.matches('chops-signin-aware')) continue;
      document.body.removeChild(child);
    }
  });

  test('update', async function() {
    const csa = document.createElement('chops-signin-aware');
    document.body.appendChild(csa);
    await afterRender();
    assert.isUndefined(csa.authHeaders);
    assert.isUndefined(csa.profile);
    assert.isFalse(csa.signedIn);

    window.getUserProfileSync = () => {
      return {};
    };
    window.getAuthorizationHeaders = async() => [];
    let userUpdateEvent;
    csa.addEventListener('user-update', event => {
      userUpdateEvent = event;
    });

    window.dispatchEvent(new CustomEvent('user-update'));
    await afterRender();
    assert.isDefined(csa.authHeaders);
    assert.isDefined(csa.profile);
    assert.isTrue(csa.signedIn);
  });
});
