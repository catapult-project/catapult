/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  const NOTIFICATION_MS = 5000;

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
      await this.dispatch('reopenClosedAlerts', this.statePath);
    }

    async onReopenClosedChart_() {
      // TODO (#4461)
    }

    async requireSignIn_(event) {
      if (this.userEmail || !this.isProduction) return;
      const auth = await window.getAuthInstanceAsync();
      await auth.signIn();
    }

    hideReportSection_(event) {
      this.dispatch(Redux.UPDATE(this.statePath, {
        showingReportSection: false,
      }));
    }

    async onShowReportSection_(event) {
      await this.dispatch(Redux.UPDATE(this.statePath, {
        showingReportSection: true,
      }));
    }

    async onNewAlertsSection_(event) {
      await this.dispatch({
        type: ChromeperfApp.reducers.newAlerts.name,
        statePath: this.statePath,
      });
    }

    async onNewChart_(event) {
      // TODO (#4461)
    }

    async onCloseAlerts_(event) {
      await this.dispatch('closeAlerts', this.statePath, event.model.id);
    }

    async onReportAlerts_(event) {
      await this.dispatch({
        type: ChromeperfApp.reducers.newAlerts.name,
        statePath: this.statePath,
        options: event.detail.options,
      });
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
    reportSection: options => cp.ReportSection.buildState({
      sources: [cp.ReportControls.DEFAULT_NAME],
    }),
    showingReportSection: options => true,
    alertsSectionIds: options => [],
    alertsSectionsById: options => {return {};},
    closedAlertsIds: options => [],
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

    closeAlerts: (statePath, sectionId) => async(dispatch, getState) => {
      dispatch({
        type: ChromeperfApp.reducers.closeAlerts.name,
        statePath,
        sectionId,
      });

      await cp.timeout(NOTIFICATION_MS);
      const state = Polymer.Path.get(getState(), statePath);
      if (!state.closedAlertsIds.includes(sectionId)) {
        // This alerts section was reopened.
        return;
      }
      dispatch({
        type: ChromeperfApp.reducers.forgetClosedAlerts.name,
        statePath,
      });
    },

    reopenClosedAlerts: statePath => async(dispatch, getState) => {
      const state = Polymer.Path.get(getState(), statePath);
      dispatch(Redux.UPDATE(statePath, {
        alertsSectionIds: [
          ...state.alertsSectionIds,
          ...state.closedAlertsIds,
        ],
        closedAlertsIds: [],
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

    newAlerts: (state, {options}, rootState) => {
      for (const alerts of Object.values(state.alertsSectionsById)) {
        // If the user mashes the ALERTS button, don't open copies of the same
        // alerts section.
        if (!cp.AlertsSection.matchesOptions(alerts, options)) continue;
        if (state.alertsSectionIds.includes(alerts.sectionId)) return state;
        return {
          ...state,
          closedAlertsIds: [],
          alertsSectionIds: [
            alerts.sectionId,
            ...state.alertsSectionIds,
          ],
        };
      }

      const sectionId = tr.b.GUID.allocateSimple();
      const newSection = cp.AlertsSection.buildState({sectionId, ...options});
      const alertsSectionsById = {...state.alertsSectionsById};
      alertsSectionsById[sectionId] = newSection;
      state = {...state};
      const alertsSectionIds = Array.from(state.alertsSectionIds);
      alertsSectionIds.push(sectionId);
      return {...state, alertsSectionIds, alertsSectionsById};
    },

    closeAlerts: (state, {sectionId}, rootState) => {
      const sectionIdIndex = state.alertsSectionIds.indexOf(sectionId);
      const alertsSectionIds = [...state.alertsSectionIds];
      alertsSectionIds.splice(sectionIdIndex, 1);
      let closedAlertsIds = [];
      if (!cp.AlertsSection.isEmpty(
          state.alertsSectionsById[sectionId])) {
        closedAlertsIds = [sectionId];
      }
      return {...state, alertsSectionIds, closedAlertsIds};
    },

    forgetClosedAlerts: (state, action, rootState) => {
      const alertsSectionsById = {...state.alertsSectionsById};
      for (const id of state.closedAlertsIds) {
        delete alertsSectionsById[id];
      }
      return {
        ...state,
        alertsSectionsById,
        closedAlertsIds: [],
      };
    },
  };

  cp.ElementBase.register(ChromeperfApp);
  return {ChromeperfApp};
});
