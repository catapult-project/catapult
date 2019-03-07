/* Copyright 2019 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';
tr.exportTo('cp', () => {
  class ReportTable extends cp.ElementBase {
    prevMstoneLabel_(milestone, maxRevision) {
      if (maxRevision === 'latest') milestone += 1;
      return `M${milestone - 1}`;
    }

    curMstoneLabel_(milestone, maxRevision) {
      if (maxRevision === 'latest') return '';
      return `M${milestone}`;
    }

    async onCopy_(event) {
      const table = document.createElement('table');
      const statisticsCount = this.statistics.length;
      for (const row of this.rows) {
        const tr = document.createElement('tr');
        table.appendChild(tr);
        // b/111692559
        const td = document.createElement('td');
        td.innerText = row.label;
        tr.appendChild(td);

        for (let scalarIndex = 0; scalarIndex < 2 * statisticsCount;
          ++scalarIndex) {
          const td = document.createElement('td');
          tr.appendChild(td);
          const scalar = row.scalars[scalarIndex];
          if (isNaN(scalar.value) || !isFinite(scalar.value)) continue;
          const scalarStr = scalar.unit.format(scalar.value, {
            unitPrefix: scalar.unitPrefix,
          });
          const numberMatch = scalarStr.match(/^(-?[,0-9]+\.?[0-9]*)/);
          if (!numberMatch) continue;
          td.innerText = numberMatch[0];
        }
      }

      this.$.scratch.appendChild(table);
      const range = document.createRange();
      range.selectNodeContents(this.$.scratch);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand('copy');
      await this.$.copied.open();
      this.$.scratch.innerText = '';
    }

    async onOpenChart_(event) {
      event.preventDefault();

      // The user may have clicked a link for an individual row (in which case
      // labelPartIndex = labelParts.length - 1) or a group of rows (in which
      // case labelPartIndex < labelParts.length - 1). In the latter case,
      // collect all parameters for all rows in the group (all measurements, all
      // bots, all test cases, all test suites).
      function getLabelPrefix(row) {
        return row.labelParts.slice(0, event.model.labelPartIndex + 1).map(
            p => p.label).join(':');
      }
      const labelPrefix = getLabelPrefix(event.model.parentModel.row);
      const suites = new Set();
      const measurements = new Set();
      const bots = new Set();
      const cases = new Set();
      for (const row of this.rows) {
        if (getLabelPrefix(row) !== labelPrefix) continue;
        for (const suite of row.suite.selectedOptions) {
          suites.add(suite);
        }
        for (const measurement of row.measurement.selectedOptions) {
          measurements.add(measurement);
        }
        for (const bot of row.bot.selectedOptions) {
          bots.add(bot);
        }
        for (const cas of row.case.selectedOptions) {
          cases.add(cas);
        }
      }
      let maxRevision = this.maxRevision;
      if (maxRevision === 'latest') {
        maxRevision = undefined;
      }

      this.dispatchEvent(new CustomEvent('new-chart', {
        bubbles: true,
        composed: true,
        detail: {
          options: {
            minRevision: this.minRevision,
            maxRevision,
            parameters: {
              suites: [...suites],
              measurements: [...measurements],
              bots: [...bots],
              cases: [...cases],
            },
          },
        },
      }));
    }

    numChangeColumns_(statistics) {
      return 2 * this.lengthOf_(statistics);
    }

    canEdit_(userEmail) {
      return ReportTable.canEdit(table, userEmail);
    }

    async onEnterRow_(event) {
      if (!event.model.row.actualDescriptors) return;
      let tr;
      for (const elem of event.path) {
        if (elem.tagName === 'TR') {
          tr = elem;
          break;
        }
      }
      if (!tr) return;
      const td = tr.querySelector('scalar-span');
      const tdRect = await cp.measureElement(td);
      const thisRect = await cp.measureElement(this);
      await this.dispatch(Redux.UPDATE(this.statePath, {
        tooltip: {
          rows: event.model.row.actualDescriptors.map(descriptor => [
            descriptor.testSuite, descriptor.bot, descriptor.testCase]),
          top: (tdRect.bottom - thisRect.bottom),
          left: (tdRect.left - thisRect.left),
        },
      }));
    }
  }

  ReportTable.canEdit = (owners, userEmail) =>
    window.IS_DEBUG ||
    (owners && userEmail && owners.includes(userEmail));

  ReportTable.State = {
    milestone: options => options.milestone,
    minRevision: options => options.minRevision,
    maxRevision: options => options.maxRevision,
    name: options => options.name || '',
    url: options => options.url || '',
    isPlaceholder: options => options.isPlaceholder || false,
    maxLabelParts: options => options.maxLabelParts || 1,
    statistics: options => options.statistics || ['avg'],
    rows: options => options.rows || [],
    owners: options => options.owners || [],
    tooltip: options => {return {};},
  };

  ReportTable.buildState = options => cp.buildState(
      ReportTable.State, options);

  ReportTable.properties = cp.buildProperties('state', ReportTable.State);

  const DASHES = '-'.repeat(5);
  const PLACEHOLDER_TABLE = {
    name: DASHES,
    isPlaceholder: true,
    statistics: ['avg'],
    report: {rows: []},
  };
  // Keep this the same shape as the default report so that the buttons don't
  // move when the default report loads.
  for (let i = 0; i < 4; ++i) {
    const scalars = [];
    for (let j = 0; j < 4 * PLACEHOLDER_TABLE.statistics.length; ++j) {
      scalars.push({value: 0, unit: tr.b.Unit.byName.count});
    }
    PLACEHOLDER_TABLE.report.rows.push({
      labelParts: [
        {
          href: '',
          label: DASHES,
          isFirst: true,
          rowCount: 1,
        },
      ],
      scalars,
    });
  }

  ReportTable.placeholderTable = name => {
    return {
      ...PLACEHOLDER_TABLE,
      name,
    };
  };

  cp.ElementBase.register(ReportTable);

  return {ReportTable};
});
