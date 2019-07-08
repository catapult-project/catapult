/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './scalar-span.js';
import {AlertDetail} from './alert-detail.js';
import {BisectDialog} from './bisect-dialog.js';
import {ChartBase} from './chart-base.js';
import {ChartTimeseries} from './chart-timeseries.js';
import {DetailsFetcher} from './details-fetcher.js';
import {ElementBase, STORE} from './element-base.js';
import {NudgeAlert} from './nudge-alert.js';
import {TimeseriesMerger} from './timeseries-merger.js';
import {UPDATE} from './simple-redux.js';
import {get} from 'dot-prop-immutable';
import {html, css} from 'lit-element';

import {
  breakWords,
  enumerate,
  isProduction,
  measureElement,
  measureText,
  plural,
} from './utils.js';

// Sort hidden rows after rows with visible labels.
const HIDE_ROW_PREFIX = String.fromCharCode('z'.charCodeAt(0) + 1).repeat(3);

const MARKDOWN_LINK_REGEX = /^\[([^\]]+)\]\(([^\)]+)\)/;

const MAX_REVISION_LENGTH = 30;

export class DetailsTable extends ElementBase {
  static get is() { return 'details-table'; }

  static get properties() {
    return {
      statePath: String,
      isLoading: Boolean,
      colorByLine: Array,
      lineDescriptors: Array,
      minRevision: Number,
      maxRevision: Number,
      revisionRanges: Array,
      commonLinkRows: Array,
      bodies: Array,
    };
  }

  static buildState(options = {}) {
    return {
      isLoading: false,
      colorByLine: [],
      lineDescriptors: options.lineDescriptors || [],
      minRevision: options.minRevision || 0,
      maxRevision: options.maxRevision || Number.MAX_SAFE_INTEGER,
      revisionRanges: options.revisionRanges || [],
      commonLinkRows: [],
      bodies: [],
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        display: flex;
        flex-direction: column;
        width: 100%;
      }
      #empty {
        min-width: 300px;
        min-height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #empty[hidden], table[hidden] {
        display: none;
      }
      table {
        box-shadow: var(--elevation-1);
        padding: 4px;
      }
      th {
        /* --color is computed by getColor_ and set in the HTML below. */
        color: var(--color);
        border-bottom: 2px solid var(--color);
        padding-top: 4px;
      }
      td {
        vertical-align: top;
      }
    `;
  }

  renderLinkRow_(row) {
    return html`
      <tr>
        <td>
          ${(row.label && !row.label.startsWith(HIDE_ROW_PREFIX)) ? html`
            ${row.label}
          ` : html`
            &nbsp;
          `}
        </td>
        ${row.cells.map(cell => html`
          <td>
            ${cell.href ? html`
              <a href="${cell.href}" target="_blank">${cell.label}</a>
            ` : html`
              ${cell.label}
            `}
          </td>
        `)}
      </tr>
    `;
  }

  renderDiagnosticsRow_(body) {
    if (!body.diagnosticsCells.filter(x => x).length) return '';

    return html`
      <tr>
        <td>Changed Diagnostics</td>
        ${body.diagnosticsCells.map(diagnostics => html`
          <td>
            ${!diagnostics ? '' : [...diagnostics.keys()].join(', ')}
          </td>
        `)}
      </tr>
    `;
  }

  renderScalarRow_(row) {
    return html`
      <tr>
        <td>${row.label}</td>
        ${row.cells.map(cell => html`
          <td>
            <scalar-span
                .value="${cell.value}"
                .unit="${cell.unit}">
            </scalar-span>
          </td>
        `)}
      </tr>
    `;
  }

  renderAlertsRow_(alertCells, bodyIndex) {
    return html`
      <tr>
        <td>Alerts</td>
        ${alertCells.map((cell, cellIndex) => html`
          <td>
            ${cell.alerts.map((alert, alertIndex) => html`
              <alert-detail .statePath="${
  this.statePath}.bodies.${bodyIndex}.alertCells.${cellIndex}.alerts.${
  alertIndex}">
              </alert-detail>
            `)}
          </td>
        `)}
      </tr>
    `;
  }

  renderBisectRow_(body, bodyIndex) {
    return html`
      <tr>
        <td>Bisect</td>
        ${body.bisectMessage ? html`
          <td colspan="99">
            ${body.bisectMessage}
          </td>
        ` : body.bisectCells.map((bisect, bisectIndex) => html`
          <td>
            <bisect-dialog .statePath="${
  this.statePath}.bodies.${bodyIndex}.bisectCells.${bisectIndex}">
            </bisect-dialog>
          </td>
        `)}
      </tr>
    `;
  }

  renderHistogram_(body, bodyIndex, cellIndex) {
    const statePath = [
      this.statePath, 'bodies', bodyIndex, 'histogramCells', cellIndex,
    ].join('.');
    const onHistogramTooltip = event => this.onHistogramTooltip_(
        statePath, event);
    const onMouseLeaveHistogram = () => this.onMouseLeaveHistogram_(statePath);
    return html`
      <chart-base
          .statePath="${statePath}"
          style="--color: ${this.getColor_(body)};"
          @get-tooltip="${onHistogramTooltip}"
          @mouse-leave-main="${onMouseLeaveHistogram}">
      </chart-base>
    `;
  }

  onHistogramTooltip_(statePath, event) {
    const bar = event.detail.nearestBar;
    const name = `${bar.count} sample${plural(bar.count)} in ${bar.binRange}`;
    STORE.dispatch(UPDATE(statePath, {tooltip: {
      isVisible: true,
      right: '100%',
      top: bar.y,
      color: 'var(--color)',
      rows: [{colspan: 2, name}],
    }}));
  }

  onMouseLeaveHistogram_(statePath) {
    STORE.dispatch(UPDATE(statePath, {tooltip: undefined}));
  }

  renderHistogramRow_(body, bodyIndex) {
    if (!body.histogramCells.filter(c => c).length) return '';

    return html`
      <tr>
        <td>Histogram</td>
        ${body.histogramCells.map((cell, cellIndex) => html`
          <td>
            ${!cell ? '' : this.renderHistogram_(body, bodyIndex, cellIndex)}
          </td>
        `)}
      </tr>
    `;
  }

  render() {
    return html`
      <chops-loading ?loading="${this.isLoading}"></chops-loading>

      <div id="empty" ?hidden="${!this.isLoading || this.bodies.length}">
        Loading details
      </div>

      <table ?hidden="${!this.bodies || (this.bodies.length === 0)}">
        <thead>
          ${(this.commonLinkRows || []).map(row => this.renderLinkRow_(row))}
        </thead>

        ${(this.bodies || []).map((body, bodyIndex) => html`
          <tbody>
            ${(this.lineDescriptors.length < 2) ? '' : html`
              <tr>
                <th colspan="99"
                    style="--color: ${this.getColor_(body)};">
                  ${body.descriptorParts.map(part => html`
                    <span>${part}</span>
                  `)}
                </th>
              </tr>
            `}

            ${body.scalarRows.map(row => this.renderScalarRow_(row))}

            ${body.linkRows.map(row => this.renderLinkRow_(row))}

            ${this.renderDiagnosticsRow_(body)}

            ${!body.histogramCells.length ? '' : this.renderHistogramRow_(
      body, bodyIndex)}

            ${!body.alertCells.length ? '' : this.renderAlertsRow_(
      body.alertCells, bodyIndex)}

            ${!body.bisectCells.length ? '' : this.renderBisectRow_(
      body, bodyIndex)}
          </tbody>
        `)}
      </table>
    `;
  }

  stateChanged(rootState) {
    if (!this.statePath) return;

    const oldLineDescriptors = this.lineDescriptors;
    const oldRevisionRanges = this.revisionRanges;

    Object.assign(this, get(rootState, this.statePath));

    if (this.lineDescriptors !== oldLineDescriptors ||
        this.revisionRanges !== oldRevisionRanges) {
      this.debounce('load', () => {
        DetailsTable.load(this.statePath);
      });
    }
  }

  getColor_(body) {
    for (const {descriptor, color} of (this.colorByLine || [])) {
      if (body.descriptor === descriptor) return color;
    }
  }

  static async load(statePath) {
    let state = get(STORE.getState(), statePath);
    if (!state) return;

    const started = performance.now();
    STORE.dispatch({
      type: DetailsTable.reducers.startLoading.name,
      statePath,
      started,
    });

    const fetcher = new DetailsFetcher(
        state.lineDescriptors,
        state.minRevision, state.maxRevision,
        state.revisionRanges);
    for await (const {timeseriesesByLine, errors} of fetcher) {
      state = get(STORE.getState(), statePath);
      if (!state || state.started !== started) return;

      STORE.dispatch({
        type: DetailsTable.reducers.receiveData.name,
        statePath,
        timeseriesesByLine,
      });
      await DetailsTable.generateTicks(statePath);
    }

    STORE.dispatch(UPDATE(statePath, {isLoading: false}));
  }

  static async generateTicks(statePath) {
    const state = get(STORE.getState(), statePath);
    const promises = [];
    for (const [bodyIndex, body] of enumerate(state.bodies)) {
      const bodyPath = statePath + '.bodies.' + bodyIndex;
      for (const [cellIndex, cell] of enumerate(body.histogramCells)) {
        if (!cell) continue;
        const cellPath = bodyPath + '.histogramCells.' + cellIndex;
        promises.push(DetailsTable.updateYAxisWidth(
            cell.yAxis.ticks, cellPath));
      }
    }
    await Promise.all(promises);
  }

  static async updateYAxisWidth(ticks, cellPath) {
    const tickRects = await Promise.all(ticks.map(tick =>
      measureText(tick.text)));
    const width = tr.b.math.Statistics.max(tickRects, rect => rect.width);
    STORE.dispatch(UPDATE(cellPath + '.yAxis', {width}));

    // TODO generate xAxis.ticks
  }

  // Factor common linkRows out to share above the bodies.
  static extractCommonLinkRows(bodies) {
    const commonLinkRows = [];
    if (bodies.length <= 1) return commonLinkRows;

    for (const linkRow of bodies[0].linkRows) {
      let isCommon = true;
      for (const body of bodies.slice(1)) {
        let isFound = false;
        for (const otherLinkRow of body.linkRows) {
          if (otherLinkRow.label !== linkRow.label) continue;

          isFound = true;
          for (const [index, cell] of enumerate(linkRow.cells)) {
            const missing = (cell === undefined);
            const otherCell = otherLinkRow.cells[index];
            const otherMissing = (otherCell === undefined);
            if (missing && otherMissing) continue;
            if (missing !== otherMissing ||
                cell.href !== otherCell.href ||
                cell.label !== otherCell.label) {
              isCommon = false;
              break;
            }
          }
          if (!isCommon) break;
        }
        if (!isFound) isCommon = false;
        if (!isCommon) break;
      }

      if (isCommon) {
        commonLinkRows.push(linkRow);
        for (const body of bodies) {
          body.linkRows = body.linkRows.filter(test =>
            test.label !== linkRow.label);
        }
      }
    }
    return commonLinkRows;
  }

  static buildCellRevisions(cell, reference, revisionInfo, links) {
    for (const [rName, r2] of Object.entries(cell.revisions)) {
      // Abbreviate git hashes.
      let label = (r2.length >= MAX_REVISION_LENGTH) ? r2.substr(0, 7) : r2;

      let r1;
      if (reference && reference.revisions && reference.revisions[rName]) {
        r1 = reference.revisions[rName];

        // If the reference revision is a number, increment it to start the
        // range *after* the reference revision.
        if (r1.match(/^\d+$/)) r1 = (parseInt(r1) + 1).toString();

        let r1Label = r1;
        if (r1.length >= MAX_REVISION_LENGTH) r1Label = r1.substr(0, 7);
        label = r1Label + ' - ' + label;
      }

      const {name, url} = ChartTimeseries.revisionLink(
          revisionInfo, rName, r1, r2);
      links.set(name, {href: url, label});
    }
  }

  static buildCellAnnotations(cell, links) {
    for (const [key, value] of Object.entries(cell.annotations || {})) {
      if (!value) continue;

      if (tr.b.isUrl(value)) {
        let label = key;
        if (label === 'a_tracing_uri') label = 'sample trace';
        links.set(HIDE_ROW_PREFIX + key, {href: value, label});
        continue;
      }

      const match = value.match(MARKDOWN_LINK_REGEX);
      if (match && match[1] && match[2]) {
        links.set(HIDE_ROW_PREFIX + key, {href: match[2], label: match[1]});
        continue;
      }
    }
  }

  static buildCellBisect(cell, reference, alerts, lineDescriptor) {
    const bisectCell = BisectDialog.buildState({
      alertKeys: alerts.map(a => a.key),
      startRevision: reference.revision + 1,
      endRevision: cell.revision,
      suite: lineDescriptor.suites[0],
      measurement: lineDescriptor.measurement,
      bot: lineDescriptor.bots[0],
      case: lineDescriptor.cases[0],
      statistic: lineDescriptor.statistic,
    });
    bisectCell.able = true;
    if (bisectCell.startRevision >= bisectCell.endRevision) {
      bisectCell.able = false;
      bisectCell.tooltip = 'Unable to bisect single revision';
    }
    return bisectCell;
  }

  static buildCellScalars(cell) {
    const scalars = new Map();
    for (const stat of ['avg', 'std', 'min', 'max', 'sum']) {
      if (cell[stat] === undefined || isNaN(cell[stat])) continue;
      scalars.set(stat, {unit: cell.unit, value: cell[stat]});
    }
    if (cell.count !== undefined) {
      scalars.set('count', {unit: tr.b.Unit.byName.count, value: cell.count});
    }
    return scalars;
  }

  static buildCellAlerts(alerts) {
    for (const alert of alerts) {
      alert.nudge = NudgeAlert.buildState({minRevision, maxRevision, ...alert});

      alert.descriptorParts = [];
      if (lineDescriptor.suites.length > 1) {
        alert.descriptorParts.push(alert.suite);
      }
      if (lineDescriptor.bots.length !== 1) {
        alert.descriptorParts.push(alert.bot);
      }
      if (lineDescriptor.cases.length !== (alert.case ? 1 : 0)) {
        alert.descriptorParts.push(alert.case || MISSING_CASE_LABEL);
      }
    }
  }

  static buildCellTimestamp(cell, links) {
    if (cell.timestampRange.min === cell.timestampRange.max) {
      if (cell.timestamp) {
        const label = tr.b.formatDate(cell.timestamp);
        links.set('Upload timestamp', {href: '', label});
      }
    } else {
      let label = tr.b.formatDate(new Date(cell.timestampRange.min));
      label += ' - ';
      label += tr.b.formatDate(new Date(cell.timestampRange.max));
      links.set('Upload timestamp', {href: '', label});
    }
  }

  // Merge timeserieses and format the detailed data as links and scalars.
  static buildCell(
      lineDescriptor, timeserieses, range, revisionInfo,
      minRevision, maxRevision,
      masterWhitelist, suiteBlacklist) {
    if (!timeserieses) return {};
    const {reference, cell} = mergeData(timeserieses, range);
    if (!cell) return {};

    const links = new Map();
    DetailsTable.buildCellRevisions(cell, reference, revisionInfo, links);
    DetailsTable.buildCellAnnotations(cell, links);
    DetailsTable.buildCellTimestamp(cell, links);
    const scalars = DetailsTable.buildCellScalars(cell);
    const alerts = cell.alerts.map(alert => AlertDetail.buildState(alert));
    const bisectCell = DetailsTable.buildCellBisect(
        cell, reference, alerts, lineDescriptor);
    DetailsTable.buildCellAlerts(alerts);
    const histogram = cell.histogram;
    const diagnostics = cell.diagnostics;

    return {scalars, links, alerts, bisectCell, histogram, diagnostics};
  }

  // Return an object containing flags indicating whether to show parts of
  // lineDescriptors in descriptorParts.
  static descriptorFlags(lineDescriptors) {
    if (lineDescriptors.length === 1) return {measurement: true};

    let suite = false;
    let measurement = false;
    let bot = false;
    let cases = false;
    let statistic = false;
    let buildType = false;
    const firstSuites = lineDescriptors[0].suites.join('\n');
    const firstBots = lineDescriptors[0].bots.join('\n');
    const firstCases = lineDescriptors[0].cases.join('\n');
    for (const other of lineDescriptors.slice(1)) {
      suite = suite || (other.suites.join('\n') !== firstSuites);
      measurement = measurement || (
        other.measurement !== lineDescriptors[0].measurement);
      bot = bot || (other.bots.join('\n') !== firstBots);
      cases = cases || (other.cases.join('\n') !== firstCases);
      statistic = statistic || (
        other.statistic !== lineDescriptors[0].statistic);
      buildType = buildType || (
        other.buildType !== lineDescriptors[0].buildType);
    }
    return {suite, measurement, bot, cases, statistic, buildType};
  }
}

// Build a table map.
function setCell(map, key, columnCount, columnIndex, value) {
  if (!map.has(key)) map.set(key, new Array(columnCount));
  map.get(key)[columnIndex] = value;
}

function removeDiagnosticRefs(hist) {
  for (const [name, diag] of hist.diagnostics) {
    if (!(diag instanceof tr.v.d.DiagnosticRef)) continue;
    hist.diagnostics.delete(name);
  }
}

function mergeHistograms(cell, datum) {
  if (!datum.histogram) return;
  if (!cell.histogram) {
    cell.histogram = datum.histogram;
    return;
  }

  // Merge Histograms if possible, otherwise ignore earlier data.
  if (cell.histogram.canAddHistogram(datum.histogram)) {
    // TODO Resolve DiagnosticRefs before here instead of removing them here.
    removeDiagnosticRefs(cell.histogram);
    removeDiagnosticRefs(datum.histogram);
    cell.histogram.addHistogram(datum.histogram);
  } else if (datum.revision > cell.revision) {
    cell.histogram = datum.histogram;
  }
}

// Merge across timeseries and data points to produce two data points
// {reference, cell}. This is different from TimeseriesMerger, which produces
// a series of data points for ChartTimeseries.
function mergeData(timeserieses, range) {
  const reference = {revisions: {}};
  let cell;
  for (const timeseries of timeserieses) {
    for (const datum of timeseries) {
      if (datum.revision < range.min) {
        if (!reference.revision ||
            datum.revision < reference.revision) {
          reference.revision = datum.revision;
          // This might overwrite some or all of reference.revisions.
          Object.assign(reference.revisions, datum.revisions);
        }
        continue;
      }

      if (!cell) {
        cell = {...datum};
        cell.timestampRange = new tr.b.math.Range();
        if (cell.timestamp) {
          cell.timestampRange.addValue(cell.timestamp.getTime());
        }
        if (!cell.revisions) cell.revisions = {};
        cell.alerts = [];
        if (cell.alert) cell.alerts.push(cell.alert);
        continue;
      }

      TimeseriesMerger.mergeStatistics(cell, datum);
      if (datum.timestamp) {
        cell.timestampRange.addValue(datum.timestamp.getTime());
      }

      if (datum.alert) cell.alerts.push(datum.alert);

      mergeHistograms(cell, datum);

      if (datum.revision > cell.revision) {
        cell.revision = datum.revision;
        Object.assign(cell.revisions, datum.revisions);
      }

      // TODO merge annotations
    }
  }
  return {reference, cell};
}

function buildHistogramCells(hists) {
  const dataRange = new tr.b.math.Range();
  for (const hist of hists) {
    if (!hist) continue;
    dataRange.addValue(hist.min);
    dataRange.addValue(hist.max);
  }

  return hists.map(hist => buildHistogram(hist, dataRange));
}

const TEXT_HEIGHT_PX = 15;  // TODO measureText

function buildHistogram(hist, dataRange) {
  if (!hist) return undefined;

  const bars = [];
  const maxCount = tr.b.math.Statistics.max(
      hist.allBins, bin => bin.count);
  const binIndices = new tr.b.math.Range();
  for (const [i, bin] of enumerate(hist.allBins)) {
    if (!bin.range.intersectsRangeExclusive(dataRange)) continue;
    binIndices.addValue(i);
  }

  if (binIndices.min === binIndices.max) {
    // Don't display the bar chart if it would only contain a single
    // uninteresting bar.
    return undefined;
  }

  binIndices.addValue(binIndices.max + 1);
  const barHeightPx = 5;
  const barsPerTick = TEXT_HEIGHT_PX / barHeightPx;
  const graphHeight = barHeightPx * binIndices.range;
  const yTicks = [];

  for (let i = binIndices.min; i < binIndices.max; ++i) {
    const bin = hist.allBins[i];
    if ((0 === (i - binIndices.min) % barsPerTick) &&
        (i < (binIndices.max - 2))) {
      yTicks.push({
        anchor: 'bottom',
        yPct: (100 * (1 - binIndices.normalize(i))) + '%',
        text: hist.unit.format(bin.range.min),
      });
    }
    if (!bin.count) continue;
    const binRange = [
      hist.unit.format(bin.range.min), hist.unit.format(bin.range.max),
    ].join(' - ');
    bars.push({
      count: bin.count,
      binRange,
      fill: 'var(--color)',
      x: '0%',
      y: (100 * (1 - binIndices.normalize(i + 1))) + '%',
      width: (100 * bin.count / maxCount) + '%',
      height: barHeightPx,
    });
  }

  const xTicks = [
    {text: '0', xPct: 0, anchor: 'start'},
    // TODO generateTicks
    {text: maxCount, xPct: '100%', anchor: 'end'},
  ];

  return ChartBase.buildState({
    bars,
    graphHeight,
    showTooltip: true,
    xAxis: {
      showTickLines: true,
      ticks: xTicks,
      height: TEXT_HEIGHT_PX,
    },
    yAxis: {
      ticks: yTicks,
      showTickLines: true,
    },
  });
}

const MISSING_CASE_LABEL = '[no case]';

// Build an array of strings to display the parts of lineDescriptor that are
// not common to all of this details-table's lineDescriptors.
function getDescriptorParts(lineDescriptor, descriptorFlags) {
  const descriptorParts = [];
  if (descriptorFlags.suite) {
    descriptorParts.push(lineDescriptor.suites.map(breakWords).join('\n'));
  }
  if (descriptorFlags.measurement) {
    descriptorParts.push(breakWords(lineDescriptor.measurement));
  }
  if (descriptorFlags.bot) {
    descriptorParts.push(lineDescriptor.bots.map(breakWords).join('\n'));
  }
  if (descriptorFlags.cases) {
    if (lineDescriptor.cases.length) {
      descriptorParts.push(lineDescriptor.cases.map(breakWords).join('\n'));
    } else {
      descriptorParts.push(MISSING_CASE_LABEL);
    }
  }
  if (descriptorFlags.statistic) {
    descriptorParts.push(lineDescriptor.statistic);
  }
  if (descriptorFlags.buildType) {
    descriptorParts.push(lineDescriptor.buildType);
  }
  return descriptorParts;
}

// Convert Map<label, cells> to [{label, cells}].
function collectRowsByLabel(rowsByLabel) {
  const labels = [...rowsByLabel.keys()].sort();
  const rows = [];
  for (const label of labels) {
    const cells = rowsByLabel.get(label) || [];
    if (cells.length === 0) continue;
    rows.push({label, cells});
  }
  return rows;
}

function buildBisectMessage(
    lineDescriptor, userEmail, masterWhitelist, suiteBlacklist) {
  if (!isProduction()) {
    return 'Bisect is not available in dev versions.';
  }
  if (!userEmail) {
    return 'Please sign in to start bisect jobs';
  }

  if (lineDescriptor.buildType === 'ref') {
    return 'Unable to bisect ref build';
  }

  const parts = [];
  if (lineDescriptor.suites.length !== 1) parts.push('suites');
  if (lineDescriptor.bots.length !== 1) parts.push('bots');
  if (lineDescriptor.cases.length > 1) parts.push('cases');
  if (parts.length > 0) {
    return 'Unable to bisect with multiple ' + parts.join(', ');
  }

  const master = lineDescriptor.bots[0].split(':')[0];
  if (masterWhitelist && !masterWhitelist.includes(master)) {
    return `Unable to bisect on ${master} bots`;
  }

  const suite = lineDescriptor.suites[0];
  if (suiteBlacklist && suiteBlacklist.includes(suite)) {
    return `Unable to bisect suite "${suite}"`;
  }

  return undefined;
}

// Build a table body {descriptorParts, scalarRows, linkRows} to display the
// detailed data in timeseriesesByRange.
function buildBody(
    {lineDescriptor, timeseriesesByRange},
    descriptorFlags, revisionInfo, userEmail,
    minRevision, maxRevision,
    masterWhitelist, suiteBlacklist) {
  const descriptorParts = getDescriptorParts(lineDescriptor, descriptorFlags);

  // getColor_() uses this to look up this body's head color in colorByLine.
  const descriptor = ChartTimeseries.stringifyDescriptor(lineDescriptor);

  const bisectMessage = buildBisectMessage(
      lineDescriptor, userEmail, masterWhitelist, suiteBlacklist);

  const columnCount = timeseriesesByRange.length;
  const scalarRowsByLabel = new Map();
  const linkRowsByLabel = new Map();
  const alertCells = new Array(columnCount);
  const bisectCells = new Array(columnCount);
  const diagnosticsCells = new Array(columnCount);

  const histograms = new Array(columnCount);
  for (const [columnIndex, {range, timeserieses}] of enumerate(
      timeseriesesByRange)) {
    const cell = DetailsTable.buildCell(
        lineDescriptor, timeserieses, range, revisionInfo,
        minRevision, maxRevision,
        masterWhitelist, suiteBlacklist);
    for (const [rowLabel, scalar] of cell.scalars || []) {
      setCell(scalarRowsByLabel, rowLabel, columnCount, columnIndex, scalar);
    }
    for (const [rowLabel, link] of cell.links || []) {
      setCell(linkRowsByLabel, rowLabel, columnCount, columnIndex, link);
    }
    if (cell.alerts) alertCells[columnIndex] = {alerts: cell.alerts};
    bisectCells[columnIndex] = cell.bisectCell;
    diagnosticsCells[columnIndex] = cell.diagnostics;
    histograms[columnIndex] = cell.histogram;
  }

  const scalarRows = collectRowsByLabel(scalarRowsByLabel);
  const linkRows = collectRowsByLabel(linkRowsByLabel);
  if (alertCells.filter(cell => cell && cell.alerts.length).length === 0) {
    alertCells.length = 0;
  }
  const histogramCells = buildHistogramCells(histograms);

  return {
    alertCells,
    bisectCells,
    bisectMessage,
    descriptor,
    descriptorParts,
    linkRows,
    scalarRows,
    diagnosticsCells,
    histogramCells,
  };
}

DetailsTable.reducers = {
  startLoading: (state, {started}, rootState) => {
    return {
      ...state,
      isLoading: true,
      started,
      commonLinkRows: [],
      bodies: [],
    };
  },

  receiveData: (state, {timeseriesesByLine}, rootState) => {
    const descriptorFlags = DetailsTable.descriptorFlags(
        state.lineDescriptors);
    const bodies = [];
    for (const timeserieses of timeseriesesByLine) {
      const body = buildBody(
          timeserieses,
          descriptorFlags, rootState.revisionInfo, rootState.userEmail,
          state.minRevision, state.maxRevision,
          rootState.bisectMasterWhitelist, rootState.bisectSuiteBlacklist);
      if (body.scalarRows.length === 0 && body.linkRows.length === 0) {
        continue;
      }
      bodies.push(body);
    }
    const commonLinkRows = DetailsTable.extractCommonLinkRows(bodies);
    return {...state, commonLinkRows, bodies};
  },
};

ElementBase.register(DetailsTable);
