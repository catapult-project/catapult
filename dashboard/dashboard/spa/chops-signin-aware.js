/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

// TODO(950011) Import this from node_modules.

import {PolymerElement} from '@polymer/polymer/polymer-element.js';

// This component adapts chops-signin to an API that is more familiar to Polymer
// components. Use this table to convert from google-signin-aware:

// google-signin-aware                    chops-signin-aware
//                         *events*
// google-signin-aware-success            user-update
// google-signin-aware-signed-out         user-update
// signed-in-changed                      user-update
//                         *properties*
// signedIn                               signedIn
// (getAuthResponse())                    authHeaders
// clientId                               (set window.AUTH_CLIENT_ID)
// scopes                                 (not supported)
// height                                 (not supported)
// theme                                  (not supported)
// (user.getBasicProfile())               profile

class ChopsSigninAware extends PolymerElement {
  static get is() {
    return 'chops-signin-aware';
  }

  static get properties() {
    return {
      authHeaders: {type: Object, notify: true, readOnly: true},
      profile: {type: Object, notify: true, readOnly: true},
      signedIn: {type: Boolean, notify: true, readOnly: true},
    };
  }

  connectedCallback() {
    this.onUserUpdate_ = this.onUserUpdate_.bind(this);
    window.addEventListener('user-update', this.onUserUpdate_);
    this.updateProperties_();
  }

  disconnectedCallback() {
    window.removeEventListener('user-update', this.onUserUpdate_);
  }

  updateProperties_() {
    return window.getAuthorizationHeaders().then((headers) => {
      this._setAuthHeaders(headers);
      this._setProfile(window.getUserProfileSync());
      this._setSignedIn(!!this.profile);
    });
  }

  onUserUpdate_() {
    return this.updateProperties_().then(() => {
      this.dispatchEvent(new CustomEvent('user-update'));
    });
  }
}

customElements.define(ChopsSigninAware.is, ChopsSigninAware);
