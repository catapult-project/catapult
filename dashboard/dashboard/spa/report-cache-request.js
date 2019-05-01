/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import {
  CacheRequestBase, READONLY, READWRITE, jsonResponse,
} from './cache-request-base.js';
import ResultChannelSender from './result-channel-sender.js';

const STORE_REPORTS = 'reports';
const STORE_METADATA = 'metadata';
const STORES = [STORE_REPORTS, STORE_METADATA];

export default class ReportCacheRequest extends CacheRequestBase {
  constructor(fetchEvent) {
    super(fetchEvent);
    this.parseRequestPromise = this.parseRequest();
    this.isTemplateDifferent_ = false;
  }

  async parseRequest() {
    const body = await this.fetchEvent.request.clone().formData();

    if (!body.has('id')) throw new Error('Missing template id');
    this.templateId = parseInt(body.get('id'));

    if (!body.has('modified')) throw new Error('Missing modified');
    this.templateModified = parseInt(body.get('modified'));

    if (!body.has('revisions')) throw new Error('Missing revisions');
    this.revisions = body.get('revisions').split(',');
  }

  async computeChannelName() {
    await this.parseRequestPromise;
    return this.fetchEvent.request.url + '?' + new URLSearchParams({
      id: this.templateId,
      modified: this.templateModified,
      revisions: this.revisions.join(','),
    });
  }

  async sendResults_() {
    const sender = new ResultChannelSender(await this.computeChannelName());
    await sender.send(this.generateResults());
    this.onResponded();
  }

  async respond() {
    this.fetchEvent.respondWith(this.responsePromise.then(jsonResponse));
    const resultsSent = this.sendResults_();
    this.fetchEvent.waitUntil(resultsSent);
    await resultsSent;
  }

  generateResults() {
    return (async function* () {
      await this.parseRequestPromise;

      const otherRequest = await this.findInProgressRequest(async other => {
        try {
          await other.parseRequestPromise;
        } catch (invalidOther) {
          return false;
        }
        if (other.templateId !== this.templateId) return false;
        return (other.revisions.join(',') === this.revisions.join(','));
      });

      if (otherRequest) {
        // Be sure to call onComplete() to remove `this` from
        // IN_PROGRESS_REQUESTS so that `otherRequest.generateResults()` doesn't
        // await `this.generateResults()`.
        this.onComplete();
        this.readNetworkPromise = otherRequest.readNetworkPromise;
      } else {
        this.readNetworkPromise = this.readNetwork_();
      }

      const winner = await Promise.race([
        this.readDatabase_().then(result => {
          return {result, source: 'database'};
        }),
        this.readNetworkPromise.then(result => {
          return {result, source: 'network'};
        }),
      ]);
      if (winner.source === 'database' && winner.result) {
        yield winner.result;
      }

      const networkResult = await this.readNetworkPromise;
      yield networkResult;
      this.scheduleWrite(networkResult);
    }).call(this);
  }

  async readNetwork_() {
    const response = await fetch(this.fetchEvent.request);
    return await response.json();
  }

  get databaseName() {
    return ReportCacheRequest.databaseName({id: this.templateId});
  }

  get databaseVersion() {
    return 1;
  }

  async upgradeDatabase(db) {
    if (db.oldVersion < 1) {
      db.createObjectStore(STORE_REPORTS);
      db.createObjectStore(STORE_METADATA);
    }
  }

  async readDatabase_() {
    const transaction = await this.transaction(STORES, READONLY);

    // Start all asynchronous actions at once then "await" only the results
    // needed.
    const reportsPromise = this.getReports_(transaction);
    const metadataPromises = {
      editable: this.getMetadata_(transaction, 'editable'),
      internal: this.getMetadata_(transaction, 'internal'),
      modified: this.getMetadata_(transaction, 'modified'),
      name: this.getMetadata_(transaction, 'name'),
      owners: this.getMetadata_(transaction, 'owners'),
      rows: this.getMetadata_(transaction, 'rows'),
      statistics: this.getMetadata_(transaction, 'statistics'),
    };

    // Check the "modified" query parameter to verify that the template was not
    // modified after storing the data on IndexedDB. Returns true if the data is
    // stale and needs to be rewritten; otherwise, false.
    const lastModified = await metadataPromises.modified;
    if (typeof lastModified !== 'number') return;
    if (lastModified !== this.templateModified) {
      this.isTemplateDifferent_ = true;
      return;
    }

    const rows = await metadataPromises.rows;

    // Rows is undefined when no data has been cached yet.
    if (!Array.isArray(rows)) return;

    const reportsByRevision = await reportsPromise;

    // Check if there are no matching revisions
    if (Object.keys(reportsByRevision).length === 0) return;

    return {
      editable: await metadataPromises.editable,
      id: this.templateId,
      internal: await metadataPromises.internal,
      name: await metadataPromises.name,
      owners: await metadataPromises.owners,
      report: {
        rows: this.mergeRowsWithReports_(rows, reportsByRevision),
        statistics: await metadataPromises.statistics,
      },
    };
  }

  // Merge row metadata with report data indexed by revision.
  mergeRowsWithReports_(rows, reportsByRevision) {
    return rows.map((row, rowIndex) => {
      const data = {};
      for (const revision of this.revisions) {
        if (!Array.isArray(reportsByRevision[revision])) continue;
        if (!reportsByRevision[revision][rowIndex]) continue;
        data[revision] = reportsByRevision[revision][rowIndex];
      }
      return {
        ...row,
        data,
      };
    });
  }

  async getReports_(transaction) {
    const reportStore = transaction.objectStore(STORE_REPORTS);
    const reportsByRevision = {};
    await Promise.all(this.revisions.map(async(revision) => {
      const reports = await reportStore.get(revision);
      if (reports) {
        reportsByRevision[revision] = reports;
      }
    }));
    return reportsByRevision;
  }

  async getMetadata_(transaction, key) {
    const metadataStore = transaction.objectStore(STORE_METADATA);
    return await metadataStore.get(key);
  }

  async writeDatabase(networkResults) {
    const {report: networkReport, ...metadata} = networkResults;
    const {rows: networkRows, statistics} = networkReport;

    const transaction = await this.transaction(STORES, READWRITE);
    await Promise.all([
      this.writeReports_(transaction, networkResults),
      this.writeMetadata_(transaction, networkResults),
    ]);

    await transaction.complete;
  }

  async writeReports_(transaction, networkResults) {
    const reportStore = transaction.objectStore(STORE_REPORTS);

    // When the report template changes, cached data may no longer be relevant.
    if (this.isTemplateDifferent_) {
      await reportStore.clear();
    }

    // Organize reports by revision to optimize for reading by revision.
    const reportsByRevision = getReportsByRevision(networkResults.report.rows);

    // Store reportsByRevision in the "reports" object store.
    for (const [revision, reports] of Object.entries(reportsByRevision)) {
      reportStore.put(reports, revision);
    }
  }

  async writeMetadata_(transaction, networkResults) {
    const metadataStore = transaction.objectStore(STORE_METADATA);

    // When the report template changes, any portion of the metadata can change.
    if (this.isTemplateDifferent_) {
      await metadataStore.clear();
    }

    const {report: networkReport, ...metadata} = networkResults;
    const {rows: networkRows, statistics} = networkReport;

    // Store everything in "rows" but "data"; that belongs in the "reports"
    // store, which is handled by `writeReports_`.
    const rows = networkRows.map(({data: _, ...row}) => row);

    metadataStore.put(rows, 'rows');
    metadataStore.put(statistics, 'statistics');
    metadataStore.put(this.templateModified, 'modified');

    for (const [key, value] of Object.entries(metadata)) {
      metadataStore.put(value, key);
    }
  }
}

ReportCacheRequest.databaseName = (options) => `report/${options.id}`;

function getReportsByRevision(networkRows) {
  const reportsByRevision = {};

  for (let i = 0; i < networkRows.length; ++i) {
    const {data} = networkRows[i];

    for (const [revision, report] of Object.entries(data)) {
      // Verify there is an array of reports for this revision.
      if (!Array.isArray(reportsByRevision[revision])) {
        reportsByRevision[revision] = [];
      }

      // Add this report to the corresponding row.
      reportsByRevision[revision][i] = report;
    }
  }

  return reportsByRevision;
}
