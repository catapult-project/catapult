/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class AlertsControls extends cp.ElementBase {
    connectedCallback() {
      super.connectedCallback();
      this.dispatch('connected', this.statePath);

      this.dispatchSources_();
    }

    async onUserUpdate_() {
      await this.dispatch('loadReportNames', this.statePath);
      await this.dispatch('loadSheriffs', this.statePath);
    }

    async onFilter_() {
      await this.dispatch(Redux.TOGGLE(this.statePath + '.showEmptyInputs'));
    }

    showMenuInput_(showEmptyInputs, thisInput, thatInput, otherInput,
        minRevision, maxRevision) {
      if (showEmptyInputs) return true;
      if (thisInput && thisInput.selectedOptions.length) return true;
      if (!thatInput || !otherInput) return true;
      if (thatInput.selectedOptions.length === 0 &&
          otherInput.selectedOptions.length === 0 &&
          !minRevision && !maxRevision) {
        // Show all inputs when they're all empty.
        return true;
      }
      return false;
    }

    showInput_(showEmptyInputs, thisInput, thatInput, menuA, menuB, menuC) {
      if (showEmptyInputs) return true;
      if (thisInput) return true;
      if (!menuA || !menuB || !menuC) return true;
      if (menuA.selectedOptions.length === 0 &&
          menuB.selectedOptions.length === 0 &&
          menuC.selectedOptions.length === 0 &&
          !thatInput) {
        // Show all inputs when they're all empty.
        return true;
      }
      return false;
    }

    arePlaceholders_(alertGroups) {
      return alertGroups === cp.AlertsTable.PLACEHOLDER_ALERT_GROUPS;
    }

    crbug_(bugId) {
      return `http://crbug.com/${bugId}`;
    }

    async dispatchSources_() {
      if (!this.sheriff || !this.bug || !this.report) return;
      const sources = await AlertsControls.compileSources(
          this.sheriff.selectedOptions,
          this.bug.selectedOptions,
          this.report.selectedOptions,
          this.minRevision, this.maxRevision,
          this.showingImprovements, this.showingTriaged);
      this.dispatchEvent(new CustomEvent('sources', {
        bubbles: true,
        composed: true,
        detail: {sources},
      }));
    }

    async onSheriffClear_(event) {
      this.dispatch(cp.MenuInput.actions.focus(this.statePath + '.sheriff'));
      this.dispatchSources_();
    }

    async onSheriffSelect_(event) {
      this.dispatchSources_();
    }

    async onBugClear_(event) {
      this.dispatch(cp.MenuInput.actions.focus(this.statePath + '.bug'));
      this.dispatchSources_();
    }

    async onBugKeyup_(event) {
      await this.dispatch('onBugKeyup', this.statePath, event.detail.value);
    }

    async onBugSelect_(event) {
      await this.dispatch(Redux.UPDATE(this.statePath, {
        showingTriaged: true,
        showingImprovements: true,
      }));
      this.dispatchSources_();
    }

    async onReportClear_(event) {
      this.dispatch(cp.MenuInput.actions.focus(this.statePath + '.report'));
      this.dispatchSources_();
    }

    async onReportSelect_(event) {
      this.dispatchSources_();
    }

    async onMinRevisionKeyup_(event) {
      await this.dispatch(Redux.UPDATE(this.statePath, {
        minRevision: event.target.value,
      }));
      this.debounce('dispatchSources', () => {
        this.dispatchSources_();
      }, Polymer.Async.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
    }

    async onMaxRevisionKeyup_(event) {
      await this.dispatch(Redux.UPDATE(this.statePath, {
        maxRevision: event.target.value,
      }));
      this.debounce('dispatchSources', () => {
        this.dispatchSources_();
      }, Polymer.Async.timeOut.after(AlertsControls.TYPING_DEBOUNCE_MS));
    }

    async onToggleImprovements_(event) {
      this.dispatch(Redux.TOGGLE(this.statePath + '.showingImprovements'));
      this.dispatchSources_();
    }

    async onToggleTriaged_(event) {
      this.dispatch(Redux.TOGGLE(this.statePath + '.showingTriaged'));
    }

    async onClickRecentlyModifiedBugs_(event) {
      await this.dispatch('toggleRecentlyModifiedBugs', this.statePath);
    }

    async onRecentlyModifiedBugsBlur_(event) {
      await this.dispatch('toggleRecentlyModifiedBugs', this.statePath);
    }

    async onClose_(event) {
      this.dispatchEvent(new CustomEvent('close-section', {
        bubbles: true,
        composed: true,
        detail: {sectionId: this.sectionId},
      }));
    }

    observeTriaged_() {
      if (this.hasTriagedNew || this.hasTriagedExisting || this.hasIgnored) {
        this.$['recent-bugs'].scrollIntoView(true);
      }
    }

    observeRecentPerformanceBugs_() {
      this.dispatch('observeRecentPerformanceBugs', this.statePath);
    }
  }

  AlertsControls.TYPING_DEBOUNCE_MS = 300;

  AlertsControls.State = {
    bug: options => cp.MenuInput.buildState({
      label: 'Bug',
      options: [],
      selectedOptions: options.bugs,
    }),
    hasTriagedNew: options => false,
    hasTriagedExisting: options => false,
    hasIgnored: options => false,
    ignoredCount: options => 0,
    maxRevision: options => options.maxRevision || '',
    minRevision: options => options.minRevision || '',
    recentlyModifiedBugs: options => [],
    report: options => cp.MenuInput.buildState({
      label: 'Report',
      options: [],
      selectedOptions: options.reports || [],
    }),
    sheriff: options => cp.MenuInput.buildState({
      label: 'Sheriff',
      options: [],
      selectedOptions: options.sheriffs || [],
    }),
    showEmptyInputs: options => options.showEmptyInputs || false,
    showingTriaged: options => options.showingTriaged || false,
    showingImprovements: options => options.showingImprovements || false,
    showingRecentlyModifiedBugs: options => false,
    triagedBugId: options => 0,
    alertGroups: options => options.alertGroups ||
      cp.AlertsTable.PLACEHOLDER_ALERT_GROUPS,
  };

  AlertsControls.observers = [
    'observeTriaged_(hasIgnored, hasTriagedExisting, hasTriagedNew)',
    'observeRecentPerformanceBugs_(recentPerformanceBugs)',
  ];

  AlertsControls.buildState = options =>
    cp.buildState(AlertsControls.State, options);

  AlertsControls.properties = {
    ...cp.buildProperties('state', AlertsControls.State),
    recentPerformanceBugs: {statePath: 'recentPerformanceBugs'},
  };

  AlertsControls.properties.areAlertGroupsPlaceholders = {
    computed: 'arePlaceholders_(alertGroups)',
  };

  AlertsControls.actions = {
    toggleRecentlyModifiedBugs: statePath => async(dispatch, getState) => {
      dispatch(Redux.TOGGLE(`${statePath}.showingRecentlyModifiedBugs`));
    },

    onBugKeyup: (statePath, bugId) => async(dispatch, getState) => {
      dispatch({
        type: AlertsControls.reducers.onBugKeyup.name,
        statePath,
        bugId,
      });
    },

    loadReportNames: statePath => async(dispatch, getState) => {
      const reportTemplateInfos = await new cp.ReportNamesRequest().response;
      const reportNames = reportTemplateInfos.map(t => t.name);
      dispatch(Redux.UPDATE(statePath + '.report', {
        options: cp.OptionGroup.groupValues(reportNames),
        label: `Reports (${reportNames.length})`,
      }));
    },

    loadSheriffs: statePath => async(dispatch, getState) => {
      const sheriffs = await new cp.SheriffsRequest().response;
      dispatch({
        type: AlertsControls.reducers.receiveSheriffs.name,
        statePath,
        sheriffs,
      });

      const state = Polymer.Path.get(getState(), statePath);
      if (state.sheriff.selectedOptions.length === 0) {
        dispatch(cp.MenuInput.actions.focus(statePath + '.sheriff'));
      }
    },

    connected: statePath => async(dispatch, getState) => {
      AlertsControls.actions.loadReportNames(statePath)(dispatch, getState);
      AlertsControls.actions.loadSheriffs(statePath)(dispatch, getState);
      dispatch({
        type: AlertsControls.reducers.receiveRecentlyModifiedBugs.name,
        statePath,
        json: localStorage.getItem('recentlyModifiedBugs'),
      });
    },

    observeRecentPerformanceBugs: statePath => async(dispatch, getState) => {
      dispatch({
        type: AlertsControls.reducers.receiveRecentPerformanceBugs.name,
        statePath,
      });
    },
  };

  AlertsControls.reducers = {
    receiveSheriffs: (state, {sheriffs}, rootState) => {
      const sheriff = cp.MenuInput.buildState({
        label: `Sheriffs (${sheriffs.length})`,
        options: sheriffs,
        selectedOptions: state.sheriff ? state.sheriff.selectedOptions : [],
      });
      return {...state, sheriff};
    },

    onBugKeyup: (state, action, rootState) => {
      const options = state.bug.options.filter(option => !option.manual);
      const bugIds = options.map(option => option.value);
      if (action.bugId.match(/^\d+$/) &&
          !bugIds.includes(action.bugId)) {
        options.unshift({
          value: action.bugId,
          label: action.bugId,
          manual: true,
        });
      }
      return {
        ...state,
        bug: {
          ...state.bug,
          options,
        },
      };
    },

    receiveRecentPerformanceBugs: (state, action, rootState) => {
      const options = rootState.recentPerformanceBugs.map(bug => {
        return {
          label: bug.id + ' ' + bug.summary,
          value: bug.id,
        };
      });
      return {...state, bug: {...state.bug, options}};
    },

    receiveRecentlyModifiedBugs: (state, {json}, rootState) => {
      if (!json) return state;
      return {...state, recentlyModifiedBugs: JSON.parse(json)};
    },
  };

  function maybeInt(x) {
    x = parseInt(x);
    return isNaN(x) ? undefined : x;
  }

  // Maximum number of alerts to count (not return) when fetching alerts for a
  // sheriff rotation. When non-zero, /api/alerts returns the number of alerts
  // that would match the datastore query (up to COUNT_LIMIT) as response.count.
  // The maximum number of alerts to return from /api/alerts is given by `limit`
  // in AlertsRequest.
  // See count_limit in Anomaly.QueryAsync() and totalCount in AlertsSection.
  const COUNT_LIMIT = 5000;

  AlertsControls.compileSources = async(
    sheriffs, bugs, reports, minRevision, maxRevision, improvements,
    showingTriaged) => {
    // Returns a list of AlertsRequest bodies. See ../api/alerts.py for
    // request body parameters.
    const revisions = {};
    minRevision = maybeInt(minRevision);
    maxRevision = maybeInt(maxRevision);
    if (minRevision !== undefined) revisions.min_end_revision = minRevision;
    if (maxRevision !== undefined) revisions.max_start_revision = maxRevision;
    const sources = [];
    for (const sheriff of sheriffs) {
      const source = {sheriff, recovered: false, ...revisions};
      source.count_limit = COUNT_LIMIT;
      source.is_improvement = improvements;
      if (!showingTriaged) source.bug_id = '';
      sources.push(source);
    }
    for (const bug of bugs) {
      sources.push({bug_id: bug, ...revisions});
    }
    if (reports.length) {
      const reportTemplateInfos = await new cp.ReportNamesRequest().response;
      for (const name of reports) {
        for (const reportId of reportTemplateInfos) {
          if (reportId.name === name) {
            sources.push({report: reportId.id, ...revisions});
            break;
          }
        }
      }
    }
    if (sources.length === 0 && (minRevision || maxRevision)) {
      sources.push(revisions);
    }
    return sources;
  };

  cp.ElementBase.register(AlertsControls);
  return {AlertsControls};
});
