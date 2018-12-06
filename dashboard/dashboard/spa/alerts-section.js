/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  const NOTIFICATION_MS = 5000;

  class AlertsSection extends cp.ElementBase {
    ready() {
      super.ready();
      this.scrollIntoView(true);
    }

    canTriage_(alertGroups) {
      const selectedAlerts = cp.AlertsTable.getSelectedAlerts(alertGroups);
      if (selectedAlerts.length === 0) return false;
      for (const alert of selectedAlerts) {
        if (alert.bugId) return false;
      }
      return true;
    }

    canUnassignAlerts_(alertGroups) {
      const selectedAlerts = cp.AlertsTable.getSelectedAlerts(alertGroups);
      for (const alert of selectedAlerts) {
        if (alert.bugId) return true;
      }
      return false;
    }

    async onSources_(event) {
      await this.dispatch('loadAlerts', this.statePath, event.detail.sources);
    }

    async onUnassign_(event) {
      await this.dispatch('changeBugId', this.statePath, 0);
    }

    onTriageNew_(event) {
      // If the user is already signed in, then require-sign-in will do nothing,
      // and openNewBugDialog will do so. If the user is not already signed in,
      // then openNewBugDialog won't, and require-sign-in will start the signin
      // flow. Users can retry triaging after completing the signin flow.
      this.dispatchEvent(new CustomEvent('require-sign-in', {
        bubbles: true,
        composed: true,
      }));
      this.dispatch('openNewBugDialog', this.statePath);
    }

    onTriageExisting_(event) {
      // If the user is already signed in, then require-sign-in will do nothing,
      // and openExistingBugDialog will do so. If the user is not already signed
      // in, then openExistingBugDialog won't, and require-sign-in will start
      // the signin flow.
      this.dispatchEvent(new CustomEvent('require-sign-in', {
        bubbles: true,
        composed: true,
      }));
      this.dispatch('openExistingBugDialog', this.statePath);
    }

    onTriageNewSubmit_(event) {
      this.dispatch('submitNewBug', this.statePath);
    }

    onTriageExistingSubmit_(event) {
      this.dispatch('submitExistingBug', this.statePath);
    }

    onIgnore_(event) {
      this.dispatch('ignore', this.statePath);
    }

    onSelectAlert_(event) {
      this.dispatch('selectAlert', this.statePath,
          event.detail.alertGroupIndex, event.detail.alertIndex);
    }
  }

  AlertsSection.State = {
    ...cp.AlertsTable.State,
    ...cp.AlertsControls.State,
    existingBug: options => cp.TriageExisting.buildState({}),
    isLoading: options => false,
    newBug: options => cp.TriageNew.buildState({}),
    selectedAlertPath: options => undefined,
    selectedAlertsCount: options => 0,
  };

  AlertsSection.buildState = options =>
    cp.buildState(AlertsSection.State, options);

  AlertsSection.properties = {
    ...cp.buildProperties('state', AlertsSection.State),
  };

  AlertsSection.actions = {
    selectAlert: (statePath, alertGroupIndex, alertIndex) =>
      async(dispatch, getState) => {
        dispatch({
          type: AlertsSection.reducers.selectAlert.name,
          statePath,
          alertGroupIndex,
          alertIndex,
        });
      },

    cancelTriagedExisting: statePath => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {
        hasTriagedExisting: false,
        triagedBugId: 0,
      }));
    },

    storeRecentlyModifiedBugs: statePath => async(dispatch, getState) => {
      const state = Polymer.Path.get(getState(), statePath);
      localStorage.setItem('recentlyModifiedBugs', JSON.stringify(
          state.recentlyModifiedBugs));
    },

    submitExistingBug: statePath => async(dispatch, getState) => {
      let state = Polymer.Path.get(getState(), statePath);
      const triagedBugId = state.existingBug.bugId;
      dispatch(Redux.UPDATE(`${statePath}.existingBug`, {isOpen: false}));
      await dispatch(AlertsSection.actions.changeBugId(
          statePath, triagedBugId));
      dispatch({
        type: AlertsSection.reducers.showTriagedExisting.name,
        statePath,
        triagedBugId,
      });
      await AlertsSection.actions.storeRecentlyModifiedBugs(statePath)(
          dispatch, getState);

      // showTriagedExisting sets hasTriagedNew and triagedBugId, causing
      // alerts-controls to display a notification. Wait a few seconds for the
      // user to notice the notification, then automatically hide it. The user
      // will still be able to access the bug by clicking Recent Bugs in
      // alerts-controls.
      await cp.timeout(NOTIFICATION_MS);
      state = Polymer.Path.get(getState(), statePath);
      if (state.triagedBugId !== triagedBugId) return;
      dispatch(AlertsSection.actions.cancelTriagedExisting(statePath));
    },

    changeBugId: (statePath, bugId) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {isLoading: true}));
      const rootState = getState();
      let state = Polymer.Path.get(rootState, statePath);
      const selectedAlerts = cp.AlertsTable.getSelectedAlerts(
          state.alertGroups);
      const alertKeys = new Set(selectedAlerts.map(a => a.key));
      try {
        const request = new cp.ExistingBugRequest({alertKeys, bugId});
        await request.response;
        dispatch({
          type: AlertsSection.reducers.removeOrUpdateAlerts.name,
          statePath,
          alertKeys,
          bugId,
        });

        state = Polymer.Path.get(getState(), statePath);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(err);
      }
      dispatch(Redux.UPDATE(statePath, {isLoading: false}));
    },

    ignore: statePath => async(dispatch, getState) => {
      let state = Polymer.Path.get(getState(), statePath);
      const alerts = cp.AlertsTable.getSelectedAlerts(state.alertGroups);
      const ignoredCount = alerts.length;
      await dispatch(AlertsSection.actions.changeBugId(statePath, -2));

      dispatch(Redux.UPDATE(statePath, {
        hasTriagedExisting: false,
        hasTriagedNew: false,
        hasIgnored: true,
        ignoredCount,
      }));

      // Setting hasIgnored and ignoredCount causes alerts-controls to display a
      // notification. Wait a few seconds for the user to notice the
      // notification, then automatically hide it. The user can still access
      // ignored alerts by toggling New Only to New and Triaged in
      // alerts-controls.
      await cp.timeout(NOTIFICATION_MS);
      state = Polymer.Path.get(getState(), statePath);
      if (state.ignoredCount !== ignoredCount) return;
      dispatch(Redux.UPDATE(statePath, {
        hasIgnored: false,
        ignoredCount: 0,
      }));
    },

    openNewBugDialog: statePath => async(dispatch, getState) => {
      let userEmail = getState().userEmail;
      if (window.IS_DEBUG) {
        userEmail = 'you@chromium.org';
      }
      if (!userEmail) return;
      dispatch({
        type: AlertsSection.reducers.openNewBugDialog.name,
        statePath,
        userEmail,
      });
    },

    openExistingBugDialog: statePath => async(dispatch, getState) => {
      let userEmail = getState().userEmail;
      if (window.IS_DEBUG) {
        userEmail = 'you@chromium.org';
      }
      if (!userEmail) return;
      dispatch({
        type: AlertsSection.reducers.openExistingBugDialog.name,
        statePath,
      });
    },

    submitNewBug: statePath => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {isLoading: true}));
      const rootState = getState();
      let state = Polymer.Path.get(rootState, statePath);
      const selectedAlerts = cp.AlertsTable.getSelectedAlerts(
          state.alertGroups);
      const alertKeys = new Set(selectedAlerts.map(a => a.key));
      let bugId;
      try {
        const request = new cp.NewBugRequest({
          alertKeys,
          ...state.newBug,
          labels: state.newBug.labels.filter(
              x => x.isEnabled).map(x => x.name),
          components: state.newBug.components.filter(
              x => x.isEnabled).map(x => x.name),
        });
        const summary = state.newBug.summary;
        bugId = await request.response;
        dispatch({
          type: AlertsSection.reducers.showTriagedNew.name,
          statePath,
          bugId,
          summary,
        });
        await AlertsSection.actions.storeRecentlyModifiedBugs(statePath)(
            dispatch, getState);

        dispatch({
          type: AlertsSection.reducers.removeOrUpdateAlerts.name,
          statePath,
          alertKeys,
          bugId,
        });
        state = Polymer.Path.get(getState(), statePath);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(err);
      }
      dispatch(Redux.UPDATE(statePath, {isLoading: false}));

      if (bugId === undefined) return;

      // showTriagedNew sets hasTriagedNew and triagedBugId, causing
      // alerts-controls to display a notification. Wait a few seconds for the
      // user to notice the notification, then automatically hide it. The user
      // will still be able to access the new bug by clicking Recent Bugs in
      // alerts-controls.
      await cp.timeout(NOTIFICATION_MS);
      state = Polymer.Path.get(getState(), statePath);
      if (state.triagedBugId !== bugId) return;
      dispatch(Redux.UPDATE(statePath, {
        hasTriagedNew: false,
        triagedBugId: 0,
      }));
    },

    loadAlerts: (statePath, sources) => async(dispatch, getState) => {
      dispatch({
        type: AlertsSection.reducers.startLoadingAlerts.name,
        statePath,
      });
      const rootState = getState();
      const state = Polymer.Path.get(rootState, statePath);

      if (sources.length > 0) {
        dispatch(cp.MenuInput.actions.blurAll());
      }

      async function wrapRequest(body) {
        const request = new cp.AlertsRequest({body});
        const response = await request.response;
        return {body, response};
      }

      const batches = new cp.BatchIterator(sources.map(wrapRequest));

      for await (const {results, errors} of batches) {
        // TODO(benjhayden): return if re-entered.
        const alerts = [];
        for (const {body, response} of results) {
          const cursor = response.next_cursor;
          // TODO(benjhayden): When should this stop chasing cursors so it
          // doesn't try to load all old alerts for this sheriff?
          if (cursor) batches.add(wrapRequest({...body, cursor}));

          alerts.push.apply(alerts, response.anomalies);
        }
        dispatch({
          type: AlertsSection.reducers.receiveAlerts.name,
          statePath,
          alerts,
          errors,
        });
        await cp.animationFrame();
      }

      dispatch({
        type: AlertsSection.reducers.finalizeAlerts.name,
        statePath,
      });
    },
  };

  AlertsSection.reducers = {
    selectAlert: (state, action, rootState) => {
      if (state.areAlertGroupsPlaceholders) return state;
      const alertPath =
        `alertGroups.${action.alertGroupIndex}.alerts.${action.alertIndex}`;
      const alert = Polymer.Path.get(state, alertPath);
      if (!alert.isSelected) {
        state = cp.setImmutable(
            state, `${alertPath}.isSelected`, true);
      }
      if (state.selectedAlertPath === alertPath) {
        return {
          ...state,
          selectedAlertPath: undefined,
        };
      }
      return {
        ...state,
        selectedAlertPath: alertPath,
      };
    },

    showTriagedNew: (state, action, rootState) => {
      return {
        ...state,
        hasTriagedExisting: false,
        hasTriagedNew: true,
        hasIgnored: false,
        triagedBugId: action.bugId,
        recentlyModifiedBugs: [
          {
            id: action.bugId,
            summary: action.summary,
          },
          ...state.recentlyModifiedBugs,
        ],
      };
    },

    showTriagedExisting: (state, action, rootState) => {
      const recentlyModifiedBugs = state.recentlyModifiedBugs.filter(bug =>
        bug.id !== action.triagedBugId);
      let triagedBugSummary = '(TODO fetch bug summary)';
      for (const bug of rootState.recentPerformanceBugs) {
        if (bug.id === action.triagedBugId) {
          triagedBugSummary = bug.summary;
          break;
        }
      }
      recentlyModifiedBugs.unshift({
        id: action.triagedBugId,
        summary: triagedBugSummary,
      });
      return {
        ...state,
        hasTriagedExisting: true,
        hasTriagedNew: false,
        hasIgnored: false,
        triagedBugId: action.triagedBugId,
        recentlyModifiedBugs,
      };
    },

    updateSelectedAlertsCount: state => {
      const selectedAlertsCount = cp.AlertsTable.getSelectedAlerts(
          state.alertGroups).length;
      return {...state, selectedAlertsCount};
    },

    removeAlerts: (state, {alertKeys}, rootState) => {
      const alertGroups = [];
      for (const group of state.alertGroups) {
        const alerts = group.alerts.filter(a => !alertKeys.has(a.key));
        if (alerts.filter(a => !a.bugId).length) {
          alertGroups.push({...group, alerts});
        }
      }
      state = {...state, alertGroups};
      return AlertsSection.reducers.updateSelectedAlertsCount(state);
    },

    updateBugId: (state, {alertKeys, bugId}, rootState) => {
      if (bugId === 0) bugId = '';
      const alertGroups = state.alertGroups.map(alertGroup => {
        const alerts = alertGroup.alerts.map(a =>
          (alertKeys.has(a.key) ? {...a, bugId} : a));
        return {...alertGroup, alerts};
      });
      state = {...state, alertGroups};
      return AlertsSection.reducers.updateSelectedAlertsCount(state);
    },

    removeOrUpdateAlerts: (state, action, rootState) => {
      if (state.showingTriaged || action.bugId === 0) {
        return AlertsSection.reducers.updateBugId(state, action, rootState);
      }
      return AlertsSection.reducers.removeAlerts(state, action, rootState);
    },

    openNewBugDialog: (state, action, rootState) => {
      const alerts = cp.AlertsTable.getSelectedAlerts(state.alertGroups);
      if (alerts.length === 0) return state;
      const newBug = cp.TriageNew.buildState({
        isOpen: true, alerts, cc: action.userEmail,
      });
      return {...state, newBug};
    },

    openExistingBugDialog: (state, action, rootState) => {
      const alerts = cp.AlertsTable.getSelectedAlerts(state.alertGroups);
      if (alerts.length === 0) return state;
      return {
        ...state,
        existingBug: {
          ...state.existingBug,
          ...cp.TriageExisting.buildState({alerts, isOpen: true}),
        },
      };
    },

    receiveAlerts: (state, {alerts, errors}, rootState) => {
      state = {
        ...state,
        selectedAlertsCount: 0,
      };

      // |alerts| are all new.
      // Group them together with previously-received alerts from
      // state.alertGroups[].alerts, which are post-transformation.
      // d.groupAlerts() requires pre-transformed objects.
      // Some previously-received alerts may have been triaged already, so we
      // can't simply accumulate pre-transformation alerts across batches.

      if (!alerts.length) {
        state = {
          ...state,
          alertGroups: cp.AlertsTable.PLACEHOLDER_ALERT_GROUPS,
          areAlertGroupsPlaceholders: true,
          showBugColumn: true,
          showMasterColumn: true,
          showTestCaseColumn: true,
        };
        if (state.sheriff.selectedOptions.length === 0 &&
            state.bug.selectedOptions.length === 0 &&
            state.report.selectedOptions.length === 0) {
          return state;
        }
        return {
          ...state,
          alertGroups: [],
          areAlertGroupsPlaceholders: false,
        };
      }

      let alertGroups = d.groupAlerts(alerts, state.showingTriaged);
      alertGroups = alertGroups.map((alerts, groupIndex) => {
        alerts = alerts.map(AlertsSection.transformAlert);
        return {
          isExpanded: false,
          alerts,
          triaged: {
            isExpanded: false,
            count: alerts.filter(a => a.bugId).length,
          }
        };
      });

      alertGroups = cp.AlertsTable.sortGroups(
          alertGroups, state.sortColumn, state.sortDescending,
          state.showingTriaged);

      // Don't automatically select the first group. Users often want to sort
      // the table by some column before previewing any alerts.

      return AlertsSection.reducers.updateColumns({
        ...state, alertGroups, areAlertGroupsPlaceholders: false,
      });
    },

    finalizeAlerts: (state, action, rootState) => {
      return {
        ...state,
        isLoading: false,
      };
    },

    updateColumns: (state, action, rootState) => {
      // Hide the Triaged, Bug, Master, and Test Case columns if they're boring.
      let showBugColumn = false;
      let showTriagedColumn = false;
      const masters = new Set();
      const testCases = new Set();
      for (const group of state.alertGroups) {
        if (group.triaged.count < group.alerts.length) {
          showTriagedColumn = true;
        }
        for (const alert of group.alerts) {
          if (alert.bugId) {
            showBugColumn = true;
          }
          masters.add(alert.master);
          testCases.add(alert.testCase);
        }
      }
      if (state.showingTriaged) showTriagedColumn = false;

      return {
        ...state,
        showBugColumn,
        showMasterColumn: masters.size > 1,
        showTestCaseColumn: testCases.size > 1,
        showTriagedColumn,
      };
    },

    startLoadingAlerts: (state, action, rootState) => {
      return {...state, isLoading: true};
    },
  };

  AlertsSection.transformAlert = alert => {
    let deltaValue = alert.median_after_anomaly -
      alert.median_before_anomaly;
    const percentDeltaValue = deltaValue / alert.median_before_anomaly;

    let improvementDirection = tr.b.ImprovementDirection.BIGGER_IS_BETTER;
    if (alert.improvement === (deltaValue < 0)) {
      improvementDirection = tr.b.ImprovementDirection.SMALLER_IS_BETTER;
    }
    const unitSuffix = tr.b.Unit.nameSuffixForImprovementDirection(
        improvementDirection);

    let baseUnit = tr.b.Unit.byName[alert.units];
    if (!baseUnit ||
        baseUnit.improvementDirection !== improvementDirection) {
      let unitName = 'unitlessNumber';
      if (tr.b.Unit.byName[alert.units + unitSuffix]) {
        unitName = alert.units;
      } else {
        const info = tr.v.LEGACY_UNIT_INFO.get(alert.units);
        if (info) {
          unitName = info.name;
          deltaValue *= info.conversionFactor || 1;
        }
      }
      baseUnit = tr.b.Unit.byName[unitName + unitSuffix];
    }
    const [master, bot] = alert.descriptor.bot.split(':');

    return {
      baseUnit,
      bot,
      bugComponents: alert.bug_components,
      bugId: alert.bug_id === undefined ? '' : alert.bug_id,
      bugLabels: alert.bug_labels,
      deltaUnit: baseUnit.correspondingDeltaUnit,
      deltaValue,
      key: alert.key,
      improvement: alert.improvement,
      isSelected: false,
      master,
      measurement: alert.descriptor.measurement,
      statistic: alert.descriptor.statistic,
      percentDeltaUnit: tr.b.Unit.byName[
          'normalizedPercentageDelta' + unitSuffix],
      percentDeltaValue,
      startRevision: alert.start_revision,
      endRevision: alert.end_revision,
      testCase: alert.descriptor.testCase,
      testSuite: alert.descriptor.testSuite,
      v1ReportLink: alert.dashboard_link,
    };
  };

  cp.ElementBase.register(AlertsSection);
  return {AlertsSection};
});
