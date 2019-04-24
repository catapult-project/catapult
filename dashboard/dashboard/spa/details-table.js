/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  // Sort hidden rows after rows with visible labels.
  const HIDE_ROW_PREFIX = String.fromCharCode('z'.charCodeAt(0) + 1).repeat(3);

  const MARKDOWN_LINK_REGEX = /^\[([^\]]+)\]\(([^\)]+)\)/;

  const MAX_REVISION_LENGTH = 30;

  class DetailsTable extends cp.ElementBase {
    static get template() {
      return Polymer.html`
        <style>
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
        </style>

        <cp-loading loading$="[[isLoading]]">
        </cp-loading>

        <div id="empty" hidden$="[[hideEmpty_(isLoading, bodies)]]">
          Loading details
        </div>

        <table hidden$="[[isEmpty_(bodies)]]">
          <thead>
            <template is="dom-repeat" items="[[commonLinkRows]]" as="row">
              <tr>
                <td>
                  <template is="dom-if" if="[[showRowLabel_(row.label)]]">
                    [[row.label]]
                  </template>
                  <template is="dom-if" if="[[!showRowLabel_(row.label)]]">
                    &nbsp;
                  </template>
                </td>
                <template is="dom-repeat" items="[[row.cells]]" as="cell">
                  <td>
                    <template is="dom-if" if="[[cell.href]]">
                      <a href="[[cell.href]]" target="_blank">[[cell.label]]</a>
                    </template>
                    <template is="dom-if" if="[[!cell.href]]">
                      [[cell.label]]
                    </template>
                  </td>
                </template>
              </tr>
            </template>
          </thead>

          <template is="dom-repeat" items="[[bodies]]" as="body">
            <tbody>
              <template is="dom-if" if="[[isMultiple_(lineDescriptors)]]">
                <tr>
                  <th colspan="99"
                      style$="--color: [[getColor_(colorByLine, body)]];">
                    <template is="dom-repeat" items="[[body.descriptorParts]]"
                                              as="part">
                      <span>[[part]]</span>
                    </template>
                  </th>
                </tr>
              </template>

              <template is="dom-repeat" items="[[body.scalarRows]]" as="row">
                <tr>
                  <td>
                    [[row.label]]
                  </td>
                  <template is="dom-repeat" items="[[row.cells]]" as="cell">
                    <td>
                      <scalar-span
                          value="[[cell.value]]"
                          unit="[[cell.unit]]">
                      </scalar-span>
                    </td>
                  </template>
                </tr>
              </template>

              <template is="dom-repeat" items="[[body.linkRows]]" as="row">
                <tr>
                  <td>
                    <template is="dom-if" if="[[showRowLabel_(row.label)]]">
                      [[row.label]]
                    </template>
                    <template is="dom-if" if="[[!showRowLabel_(row.label)]]">
                      &nbsp;
                    </template>
                  </td>
                  <template is="dom-repeat" items="[[row.cells]]" as="cell">
                    <td>
                      <template is="dom-if" if="[[cell.href]]">
                        <a href="[[cell.href]]" target="_blank">
                          [[cell.label]]
                        </a>
                      </template>
                      <template is="dom-if" if="[[!cell.href]]">
                        [[cell.label]]
                      </template>
                    </td>
                  </template>
                </tr>
              </template>
            </tbody>
          </template>
        </table>
      `;
    }

    observeConfig_(lineDescriptors, revisionRanges) {
      this.debounce('load', () => {
        this.dispatch('load', this.statePath);
      }, Polymer.Async.microTask);
    }

    getColor_(colorByLine, body) {
      for (const {descriptor, color} of (colorByLine || [])) {
        if (body.descriptor === descriptor) return color;
      }
    }

    showRowLabel_(label) {
      return label && !label.startsWith(HIDE_ROW_PREFIX);
    }

    hideEmpty_(isLoading, bodies) {
      return !isLoading || !this.isEmpty_(bodies);
    }
  }

  DetailsTable.State = {
    isLoading: options => false,
    colorByLine: options => [],
    lineDescriptors: options => options.lineDescriptors || [],
    minRevision: options => options.minRevision || 0,
    maxRevision: options => options.maxRevision || Number.MAX_SAFE_INTEGER,
    revisionRanges: options => options.revisionRanges || [],
    commonLinkRows: options => [],
    bodies: options => [],
  };

  DetailsTable.properties = cp.buildProperties(
      'state', DetailsTable.State);
  DetailsTable.buildState = options => cp.buildState(
      DetailsTable.State, options);
  DetailsTable.observers = [
    'observeConfig_(lineDescriptors, revisionRanges)',
  ];

  DetailsTable.actions = {
    load: statePath => async(dispatch, getState) => {
      let state = Polymer.Path.get(getState(), statePath);
      if (!state) return;

      const started = performance.now();
      dispatch({
        type: DetailsTable.reducers.startLoading.name,
        statePath,
        started,
      });

      const fetcher = new cp.DetailsFetcher(
          state.lineDescriptors,
          state.minRevision, state.maxRevision,
          state.revisionRanges);
      for await (const {timeseriesesByLine, errors} of fetcher) {
        state = Polymer.Path.get(getState(), statePath);
        if (!state || state.started !== started) break;

        dispatch({
          type: DetailsTable.reducers.receiveData.name,
          statePath,
          timeseriesesByLine,
        });
      }

      dispatch({type: DetailsTable.reducers.doneLoading.name, statePath});
    },
  };

  // Build a table map.
  function setCell(map, key, columnCount, columnIndex, value) {
    if (!map.has(key)) map.set(key, new Array(columnCount));
    map.get(key)[columnIndex] = value;
  }

  function mergeHistograms(cell, datum) {
    if (datum.histogram) {
      if (cell.histogram) {
        // Merge Histograms if possible, otherwise ignore earlier data.
        if (cell.histogram.canAddHistogram(datum.histogram)) {
          try {
            cell.histogram.addHistogram(datum.histogram);
          } catch (err) {
            // TODO resolve DiagnosticRefs and remove this try-catch.
          }
        } else if (datum.revision > cell.revision) {
          cell.histogram = datum.histogram;
        }
      } else {
        cell.histogram = datum.histogram;
      }
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
          continue;
        }

        cp.TimeseriesMerger.mergeStatistics(cell, datum);
        if (datum.timestamp) {
          cell.timestampRange.addValue(datum.timestamp.getTime());
        }

        // TODO Uncomment when Histograms are displayed.
        // mergeHistograms(cell, datum);

        if (datum.revision > cell.revision) {
          cell.revision = datum.revision;
          Object.assign(cell.revisions, datum.revisions);
        }

        // TODO merge annotations
      }
    }
    return {reference, cell};
  }

  // Merge timeserieses and format the detailed data as links and scalars.
  DetailsTable.buildCell = (setLink, setScalar, timeserieses, range,
      revisionInfo) => {
    const {reference, cell} = mergeData(timeserieses, range);
    if (!cell) return;

    for (const stat of ['avg', 'std', 'min', 'max', 'sum']) {
      if (cell[stat] === undefined || isNaN(cell[stat])) continue;
      setScalar(stat, cell[stat], cell.unit);
    }
    if (cell.count !== undefined) {
      setScalar('count', cell.count, tr.b.Unit.byName.count);
    }

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

      const {name, url} = cp.ChartTimeseries.revisionLink(
          revisionInfo, rName, r1, r2);
      setLink(name, url, label);
    }

    for (const [key, value] of Object.entries(cell.annotations || {})) {
      if (!value) continue;

      if (tr.b.isUrl(value)) {
        let label = key;
        if (label === 'a_tracing_uri') label = 'sample trace';
        setLink(HIDE_ROW_PREFIX + key, value, label);
        continue;
      }

      const match = value.match(MARKDOWN_LINK_REGEX);
      if (match && match[1] && match[2]) {
        setLink(HIDE_ROW_PREFIX + key, match[2], match[1]);
        continue;
      }
    }

    if (cell.timestampRange.min === cell.timestampRange.max) {
      setLink('Upload timestamp', '', tr.b.formatDate(cell.timestamp));
    } else {
      let label = tr.b.formatDate(new Date(cell.timestampRange.min));
      label += ' - ';
      label += tr.b.formatDate(new Date(cell.timestampRange.max));
      setLink('Upload timestamp', '', label);
    }
  };

  // Build an array of strings to display the parts of lineDescriptor that are
  // not common to all of this details-table's lineDescriptors.
  function getDescriptorParts(lineDescriptor, descriptorFlags) {
    const descriptorParts = [];
    if (descriptorFlags.suite) {
      descriptorParts.push(lineDescriptor.suites.map(cp.breakWords).join('\n'));
    }
    if (descriptorFlags.measurement) {
      descriptorParts.push(cp.breakWords(lineDescriptor.measurement));
    }
    if (descriptorFlags.bot) {
      descriptorParts.push(lineDescriptor.bots.map(cp.breakWords).join('\n'));
    }
    if (descriptorFlags.cases) {
      descriptorParts.push(lineDescriptor.cases.map(cp.breakWords).join('\n'));
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

  // Build a table body {descriptorParts, scalarRows, linkRows} to display the
  // detailed data in timeseriesesByRange.
  function buildBody({lineDescriptor, timeseriesesByRange}, descriptorFlags,
      revisionInfo) {
    const descriptorParts = getDescriptorParts(lineDescriptor, descriptorFlags);

    // getColor_() uses this to look up this body's head color in colorByLine.
    const descriptor = cp.ChartTimeseries.stringifyDescriptor(lineDescriptor);

    const scalarRowsByLabel = new Map();
    const linkRowsByLabel = new Map();
    const columnCount = timeseriesesByRange.length;
    for (const [columnIndex, {range, timeserieses}] of cp.enumerate(
        timeseriesesByRange)) {
      const setScalar = (rowLabel, value, unit) => setCell(
          scalarRowsByLabel, rowLabel, columnCount, columnIndex, {value, unit});
      const setLink = (rowLabel, href, label) => setCell(
          linkRowsByLabel, rowLabel, columnCount, columnIndex, {href, label});

      DetailsTable.buildCell(setLink, setScalar, timeserieses, range,
          revisionInfo);
    }

    const scalarRows = collectRowsByLabel(scalarRowsByLabel);
    const linkRows = collectRowsByLabel(linkRowsByLabel);
    return {descriptor, descriptorParts, scalarRows, linkRows};
  }

  // Return an object containing flags indicating whether to show parts of
  // lineDescriptors in descriptorParts.
  DetailsTable.descriptorFlags = lineDescriptors => {
    let suite = false;
    let measurement = false;
    let bot = false;
    let cases = false;
    let buildType = false;
    const firstSuites = lineDescriptors[0].suites.join('\n');
    const firstBots = lineDescriptors[0].bots.join('\n');
    const firstCases = lineDescriptors[0].cases.join('\n');
    for (const other of lineDescriptors.slice(1)) {
      if (!suite && other.suites.join('\n') !== firstSuites) {
        suite = true;
      }
      if (!measurement &&
          other.measurement !== lineDescriptors[0].measurement) {
        measurement = true;
      }
      if (!bot && other.bots.join('\n') !== firstBots) {
        bot = true;
      }
      if (!cases && other.cases.join('\n') !== firstCases) {
        cases = true;
      }
      if (!buildType && other.buildType !== lineDescriptors[0].buildType) {
        buildType = true;
      }
    }
    return {suite, measurement, bot, cases, buildType};
  };

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
            timeserieses, descriptorFlags, rootState.revisionInfo);
        if (body.scalarRows.length === 0 && body.linkRows.length === 0) {
          continue;
        }
        bodies.push(body);
      }
      const commonLinkRows = DetailsTable.extractCommonLinkRows(bodies);
      return {...state, commonLinkRows, bodies};
    },

    doneLoading: (state, action, rootState) => {
      return {...state, isLoading: false};
    },
  };

  // Factor common linkRows out to share above the bodies.
  DetailsTable.extractCommonLinkRows = bodies => {
    const commonLinkRows = [];
    if (bodies.length <= 1) return commonLinkRows;

    for (const linkRow of bodies[0].linkRows) {
      let isCommon = true;
      for (const body of bodies.slice(1)) {
        let isFound = false;
        for (const otherLinkRow of body.linkRows) {
          if (otherLinkRow.label !== linkRow.label) continue;

          isFound = true;
          for (const [index, cell] of cp.enumerate(linkRow.cells)) {
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
  };

  cp.ElementBase.register(DetailsTable);
  return {DetailsTable};
});
