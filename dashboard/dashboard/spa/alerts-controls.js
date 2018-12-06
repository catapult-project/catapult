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
    }

    showSheriff_(bug, report) {
      return ((bug.selectedOptions.length === 0) &&
              (report.selectedOptions.length === 0));
    }

    showBug_(sheriff, report) {
      return ((sheriff.selectedOptions.length === 0) &&
              (report.selectedOptions.length === 0));
    }

    showReport_(sheriff, bug) {
      return ((sheriff.selectedOptions.length === 0) &&
              (bug.selectedOptions.length === 0));
    }

    crbug_(bugId) {
      return `http://crbug.com/${bugId}`;
    }

    summary_(showingTriaged, alertGroups) {
      return AlertsControls.summary(showingTriaged, alertGroups);
    }

    async dispatchSources_() {
      const sources = await AlertsControls.compileSources(
          this.sheriff.selectedOptions,
          this.bug.selectedOptions,
          this.report.selectedOptions,
          this.minRevision, this.maxRevision,
          this.showingImprovements);
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
      this.dispatchSources_();
    }

    async onReportClear_(event) {
      this.dispatch(cp.MenuInput.actions.focus(this.statePath + '.report'));
      this.dispatchSources_();
    }

    async onReportKeyup_(event) {
      await this.dispatch('onReportKeyup', this.statePath, event.detail.value);
    }

    async onReportSelect_(event) {
      this.dispatchSources_();
    }

    async onMinRevisionKeyup_(event) {
      this.dispatch(Redux.UPDATE(this.statePath, {
        minRevision: event.detail.value,
      }));
      this.dispatchSources_();
    }

    async onMaxRevisionKeyup_(event) {
      this.dispatch(Redux.UPDATE(this.statePath, {
        maxRevision: event.detail.value,
      }));
      this.dispatchSources_();
    }

    async onToggleImprovements_(event) {
      this.dispatch(Redux.TOGGLE(this.statePath + '.showingImprovements'));
      this.dispatchSources_();
    }

    async onToggleTriaged_(event) {
      this.dispatch(Redux.TOGGLE(this.statePath + '.showingTriaged'));
    }

    async onTapRecentlyModifiedBugs_(event) {
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
    showingImprovements: options => options.showingImprovements || false,
    showingRecentlyModifiedBugs: options => false,
    triagedBugId: options => 0,
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

    connected: statePath => async(dispatch, getState) => {
      AlertsControls.actions.loadReportNames(statePath)(dispatch, getState);
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

  AlertsControls.compileSources = async(
    sheriffs, bugs, reports, minRevision, maxRevision, improvements) => {
    // Returns a list of AlertsRequest bodies. See ../api/alerts.py for
    // request body parameters.
    const revisions = {
      min_end_revision: maybeInt(minRevision),
      max_start_revision: maybeInt(maxRevision),
    };
    const sources = [];
    for (const sheriff of sheriffs) {
      sources.push({
        sheriff,
        is_improvement: improvements,
        ...revisions,
      });
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
    return sources;
  };

  AlertsControls.summary = (showingTriaged, alertGroups) => {
    if (!alertGroups) return '';
    let groups = 0;
    let total = 0;
    for (const group of alertGroups) {
      if (showingTriaged) {
        ++groups;
        total += group.alerts.length;
      } else if (group.alerts.length > group.triaged.count) {
        ++groups;
        total += group.alerts.length - group.triaged.count;
      }
    }
    return (
      `${total} alert${cp.plural(total)} in ` +
      `${groups} group${cp.plural(groups)}`);
  };

  cp.ElementBase.register(AlertsControls);
  return {AlertsControls};
});
