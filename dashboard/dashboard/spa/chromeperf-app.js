/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ChromeperfApp extends cp.ElementBase {
    async ready() {
      super.ready();
      const routeParams = new URLSearchParams(this.route.path);
      this.dispatch('ready', this.statePath, routeParams);
    }

    escapedUrl_(path) {
      return encodeURIComponent(window.location.origin + '#' + path);
    }

    observeReduxRoute_() {
      this.route = {prefix: '', path: this.reduxRoutePath};
    }

    async onUserUpdate_() {
      await this.dispatch('userUpdate', this.statePath);
    }

    async onReopenClosedAlerts_(event) {
      // TODO (#4461)
    }

    async onReopenClosedChart_() {
      // TODO (#4461)
    }

    async onShowReportSection_(event) {
      // TODO (#4461)
    }

    async onNewAlertsSection_(event) {
      // TODO (#4461)
    }

    async onNewChart_(event) {
      // TODO (#4461)
    }

    async onCloseAllCharts_(event) {
      // TODO (#4461)
    }

    isInternal_(userEmail) {
      return userEmail.endsWith('@google.com');
    }

    get isProduction() {
      return window.IS_PRODUCTION;
    }
  }

  ChromeperfApp.State = {
    enableNav: options => true,
    isLoading: options => true,
    // App-route sets |route|, and redux sets |reduxRoutePath|.
    // ChromeperfApp translates between them.
    // https://stackoverflow.com/questions/41440316
    reduxRoutePath: options => '',
    vulcanizedDate: options => options.vulcanizedDate,
  };

  ChromeperfApp.properties = {
    ...cp.buildProperties('state', ChromeperfApp.State),
    route: {type: Object},
    userEmail: {statePath: 'userEmail'},
  };

  ChromeperfApp.observers = [
    'observeReduxRoute_(reduxRoutePath)',
  ];

  ChromeperfApp.actions = {
    ready: (statePath, routeParams) =>
      async(dispatch, getState) => {
        dispatch(Redux.CHAIN(
            Redux.ENSURE(statePath),
            Redux.ENSURE('userEmail', ''),
        ));

        // Wait for ChromeperfApp and its reducers to be registered.
        await cp.afterRender();

        dispatch({
          type: ChromeperfApp.reducers.ready.name,
          statePath,
        });

        if (window.IS_PRODUCTION) {
          // Wait for gapi.auth2 to load and get an Authorization token.
          await window.getAuthInstanceAsync();
        }

        // The app is done loading.
        dispatch(Redux.UPDATE(statePath, {
          isLoading: false,
        }));
      },

    userUpdate: statePath => async(dispatch, getState) => {
      const profile = await window.getUserProfileAsync();
      dispatch(Redux.UPDATE('', {
        userEmail: profile ? profile.getEmail() : '',
      }));
      new TestSuitesRequest({}).response;
    },
  };

  ChromeperfApp.reducers = {
    ready: (state, action, rootState) => {
      let vulcanizedDate = '';
      if (window.VULCANIZED_TIMESTAMP) {
        vulcanizedDate = tr.b.formatDate(new Date(
            VULCANIZED_TIMESTAMP.getTime() - (1000 * 60 * 60 * 7))) + ' PT';
      }
      return cp.buildState(ChromeperfApp.State, {vulcanizedDate});
    },
  };

  cp.ElementBase.register(ChromeperfApp);
  return {ChromeperfApp};
});
