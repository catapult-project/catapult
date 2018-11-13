/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class TriageNew extends cp.ElementBase {
    ready() {
      super.ready();
      this.addEventListener('blur', this.onBlur_.bind(this));
      this.addEventListener('keyup', this.onKeyup_.bind(this));
    }

    async onKeyup_(event) {
      if (event.key === 'Escape') {
        await this.dispatch('close', this.statePath);
      }
    }

    async onBlur_(event) {
      if (event.relatedTarget === this ||
          cp.isElementChildOf(event.relatedTarget, this)) {
        return;
      }
      await this.dispatch('close', this.statePath);
    }

    observeIsOpen_() {
      if (this.isOpen) {
        this.$.description.focus();
      }
    }

    async onSummary_(event) {
      await this.dispatch('summary', this.statePath, event.target.value);
    }

    async onDescription_(event) {
      if (event.ctrlKey && (event.key === 'Enter')) {
        await this.onSubmit_(event);
        return;
      }
      await this.dispatch('description', this.statePath, event.target.value);
    }

    async onLabel_(event) {
      await this.dispatch('label', this.statePath, event.model.label.name);
    }

    async onComponent_(event) {
      await this.dispatch('component', this.statePath,
          event.model.component.name);
    }

    async onOwner_(event) {
      await this.dispatch('owner', this.statePath, event.target.value);
    }

    async onCC_(event) {
      await this.dispatch('cc', this.statePath, event.target.value);
    }

    async onSubmit_(event) {
      await this.dispatch('close', this.statePath);
      this.dispatchEvent(new CustomEvent('submit', {
        bubbles: true,
        composed: true,
      }));
    }
  }

  TriageNew.State = {
    cc: options => options.cc || '',
    components: options => TriageNew.collectAlertProperties(
        options.alerts, 'bugComponents'),
    description: options => '',
    isOpen: {
      value: options => options.isOpen || false,
      reflectToAttribute: true,
    },
    labels: options => TriageNew.collectAlertProperties(
        options.alerts, 'bugLabels'),
    owner: options => '',
    summary: options => TriageNew.summarize(options.alerts),
  };

  TriageNew.buildState = options => cp.buildState(TriageNew.State, options);
  TriageNew.properties = cp.buildProperties('state', TriageNew.State);
  TriageNew.observers = [
    'observeIsOpen_(isOpen)',
  ];

  TriageNew.actions = {
    close: statePath => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {isOpen: false}));
    },

    summary: (statePath, summary) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {summary}));
    },

    owner: (statePath, owner) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {owner}));
    },

    cc: (statePath, cc) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {cc}));
    },

    description: (statePath, description) => async(dispatch, getState) => {
      dispatch(Redux.UPDATE(statePath, {description}));
    },

    label: (statePath, name) => async(dispatch, getState) => {
      dispatch({
        type: TriageNew.reducers.toggleLabel.name,
        statePath,
        name,
      });
    },

    component: (statePath, name) => async(dispatch, getState) => {
      dispatch({
        type: TriageNew.reducers.toggleComponent.name,
        statePath,
        name,
      });
    },
  };

  TriageNew.reducers = {
    toggleLabel: (state, action, rootState) => {
      for (let i = 0; i < state.labels.length; ++i) {
        if (state.labels[i].name === action.name) {
          return cp.setImmutable(
              state, `labels.${i}.isEnabled`, e => !e);
        }
      }
      return state;
    },

    toggleComponent: (state, action, rootState) => {
      for (let i = 0; i < state.components.length; ++i) {
        if (state.components[i].name === action.name) {
          return cp.setImmutable(
              state, `components.${i}.isEnabled`, e => !e);
        }
      }
      return state;
    },
  };

  TriageNew.summarize = alerts => {
    if (!alerts) return '';
    const pctDeltaRange = new tr.b.math.Range();
    const revisionRange = new tr.b.math.Range();
    let measurements = new Set();
    for (const alert of alerts) {
      if (!alert.improvement) {
        pctDeltaRange.addValue(Math.abs(100 * alert.percentDeltaValue));
      }
      // TODO handle non-numeric revisions
      revisionRange.addValue(alert.startRevision);
      revisionRange.addValue(alert.endRevision);
      measurements.add(alert.measurement);
    }
    measurements = Array.from(measurements);
    measurements.sort((x, y) => x.localeCompare(y));
    measurements = measurements.join(',');

    let pctDeltaString = pctDeltaRange.min.toLocaleString(undefined, {
      maximumFractionDigits: 1,
    }) + '%';
    if (pctDeltaRange.min !== pctDeltaRange.max) {
      pctDeltaString += '-' + pctDeltaRange.max.toLocaleString(undefined, {
        maximumFractionDigits: 1,
      }) + '%';
    }

    let revisionString = revisionRange.min;
    if (revisionRange.min !== revisionRange.max) {
      revisionString += ':' + revisionRange.max;
    }

    return (
      `${pctDeltaString} regression in ${measurements} at ${revisionString}`
    );
  };

  TriageNew.collectAlertProperties = (alerts, property) => {
    if (!alerts) return [];
    let labels = new Set();
    if (property === 'bugLabels') {
      labels.add('Pri-2');
      labels.add('Type-Bug-Regression');
    }
    for (const alert of alerts) {
      for (const label of alert[property]) {
        labels.add(label);
      }
    }
    labels = Array.from(labels);
    labels.sort((x, y) => x.localeCompare(y));
    return labels.map(name => {
      return {name, isEnabled: true};
    });
  };

  cp.ElementBase.register(TriageNew);

  return {TriageNew};
});
