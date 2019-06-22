/* Copyright 2018 The Chromium Authors. All rights reserved.
   Use of this source code is governed by a BSD-style license that can be
   found in the LICENSE file.
*/
'use strict';

import './cp-icon.js';
import './column-head.js';
import './cp-checkbox.js';
import './expand-button.js';
import './scalar-span.js';
import {ElementBase, STORE} from './element-base.js';
import {breakWords, crbug, get, setImmutable} from './utils.js';
import {html, css, unsafeCSS, svg} from 'lit-element';

export default class AlertsTable extends ElementBase {
  static get is() { return 'alerts-table'; }

  static get properties() {
    return {
      areAlertGroupsPlaceholders: Boolean,
      statePath: String,
      previousSelectedAlertKey: String,
      alertGroups: Array,
      selectedAlertsCount: Number,
      sheriff: Object,
      showBugColumn: Boolean,
      showMasterColumn: Boolean,
      showCaseColumn: Boolean,
      showTriagedColumn: Boolean,
      showingTriaged: Boolean,
      sortColumn: String,
      sortDescending: Boolean,
    };
  }

  static buildState(options = {}) {
    return {
      previousSelectedAlertKey: undefined,
      alertGroups: options.alertGroups ||
        AlertsTable.placeholderAlertGroups(),
      selectedAlertsCount: 0,
      showBugColumn: options.showBugColumn !== false,
      showMasterColumn: options.showMasterColumn !== false,
      showCaseColumn: options.showCaseColumn !== false,
      showTriagedColumn: options.showTriagedColumn !== false,
      showingTriaged: options.showingTriaged || false,
      sortColumn: options.sortColumn || 'startRevision',
      sortDescending: options.sortDescending || false,
    };
  }

  static get styles() {
    // Depending on the screen size and alert data, this should be enough for a
    // few rows:
    const minTableHeight = 120;

    // The height of everything in alerts-section except alerts-table:
    const nonTableHeight = 620;

    const maxScreenHeight = minTableHeight + nonTableHeight;

    // TODO Use flex column in alerts-section instead of computing heights.

    return css`
      #cat {
        display: block;
        fill: var(--primary-color-medium, blue);
        height: 300px;
        width: 300px;
      }

      #scroll {
        max-height: calc(100vh - ${unsafeCSS(nonTableHeight)}px);
        margin: 0;
        overflow-y: auto;
        overflow-x: hidden;
      }

      @media screen and (max-height: ${unsafeCSS(maxScreenHeight)}px) {
        #scroll {
          height: ${unsafeCSS(minTableHeight)}px;
          max-height: ${unsafeCSS(minTableHeight)}px;
        }
      }

      table {
        border-collapse: collapse;
        width: 100%;
      }

      table[placeholder] {
        color: var(--neutral-color-dark, grey);
      }

      th {
        padding: 8px;
        white-space: nowrap;
      }

      th.checkbox {
        padding-left: 4px;
        text-align: left;
      }

      td {
        padding: 4px;
      }

      tbody tr:hover {
        background: #eee;
      }

      td:last-child {
        padding-right: 0;
      }

      expand-button {
        align-items: center;
        justify-content: flex-end;
        margin-right: 16px;
      }

      tbody {
        border-color: var(--background-color, white);
        border-style: solid;
        border-width: 0 8px;
        transition: border-width var(--transition-short, 0.2s);
      }

      tbody[expandedGroup] {
        border-color: var(--primary-color-light, lightblue);
        border-width: 8px;
      }

      tr[untriaged] {
        font-weight: bold;
      }
    `;
  }

  renderCat() {
    const PATHS = [
      'M540.27,671.672c-0.492,0.493-11.928,12.421-33.991,15.211c-21.053,2.627' +
      '-46.274-7.934-50.077-28.287 c-0.056-0.272-0.385-0.383-0.452-0.656c21.2' +
      '42-8.59,42.28-33.704,42.28-44.483c0-26.865-20.396-32.117-55.594-32.117' +
      ' c-44.757,0-55.7,6.285-55.7,32.117c0,12.688,21.366,36.003,42.65,43.991' +
      'c-0.145,0.438-0.629,0.657-0.711,1.088 c-3.967,20.962-28.924,31.03-49.4' +
      '63,28.349c-21.94-2.79-33.321-14.718-33.704-15.102c-5.171-5.744-14.069-' +
      '6.244-19.78-1.039 c-5.745,5.144-6.245,14.007-1.067,19.752c0.739,0.82,1' +
      '8.303,20.025,50.968,24.186c3.386,0.438,6.812,0.655,10.287,0.655 c21.38' +
      '7,0,42.842-8.974,56.656-25.06c14.121,16.031,35.966,25.06,57.277,25.06c' +
      '3.406,0,6.703-0.219,9.999-0.655 c32.774-4.159,50.379-23.364,51.104-24.' +
      '186c5.129-5.689,4.704-14.39-1-19.588C554.428,665.708,545.469,666.092,5' +
      '40.27,671.672z M442.435,647.051c-18.33,0-41.447-27.035-41.692-33.596c0' +
      '-13.568,0-18.109,41.692-18.109c41.587,0,41.587,8.37,41.615,17.781 C482' +
      '.736,620.076,459.346,647.051,442.435,647.051z',
      'M552.746,620.896c4.049,0,7.331-3.398,7.331-7.332c0-4.104-3.282-7.388-7' +
      '.331-7.388c-3.994,0-7.332,3.283-7.332,7.388 C545.414,617.498,548.752,6' +
      '20.896,552.746,620.896z',
      'M534.306,656.461c3.98,0,7.277-3.337,7.277-7.331c0-4.049-3.297-7.332-7.' +
      '277-7.332c-3.994,0-7.332,3.283-7.332,7.332 C526.974,653.124,530.312,65' +
      '6.461,534.306,656.461z',
      'M567.518,649.13c0,3.994,3.283,7.331,7.332,7.331c3.98,0,7.277-3.337,7.2' +
      '77-7.331c0-4.049-3.297-7.332-7.277-7.332 C570.802,641.798,567.518,645.' +
      '081,567.518,649.13z',
      'M334.702,606.178c-3.994,0-7.332,3.283-7.332,7.388c0,3.934,3.337,7.332,' +
      '7.332,7.332c3.986,0,7.276-3.398,7.276-7.332 C341.978,609.461,338.688,6' +
      '06.178,334.702,606.178z',
      'M323.54,649.13c0-4.049-3.345-7.332-7.277-7.332c-4.049,0-7.332,3.283-7.' +
      '332,7.332c0,3.994,3.283,7.331,7.332,7.331 C320.195,656.461,323.54,653.' +
      '124,323.54,649.13z',
      'M356.751,656.461c3.987,0,7.332-3.337,7.332-7.331c0-4.049-3.345-7.332-7' +
      '.332-7.332c-3.939,0-7.332,3.283-7.332,7.332 C349.42,653.124,352.812,65' +
      '6.461,356.751,656.461z',
      'M341.076,502.384c0.19-2.188,4.507-53.84-32.721-82.456c-14.035-10.751-3' +
      '0.811-16.223-49.791-16.223 c-22.986,0-40.927,8.159-41.7,8.48c-2.4,1.12' +
      '9-3.987,3.502-4.076,6.155c-0.048,2.106-1.122,51.761,34.041,77.478 c16.' +
      '086,11.654,35.071,17.562,56.355,17.562h0.027c18.903,0,32.665-4.868,33.' +
      '239-5.032 C339.024,507.418,340.83,505.064,341.076,502.384z M296.948,46' +
      '0.444c-9.745,0-17.673-7.906-17.673-17.591 c0-9.794,7.928-17.618,17.673' +
      '-17.618c9.739,0,17.666,7.824,17.666,17.618C314.614,452.538,306.687,460' +
      '.444,296.948,460.444z',
      'M680.834,411.748c-0.712-0.328-18.713-8.479-41.748-8.479c-18.986,0-35.7' +
      '29,5.471-49.806,16.223 c-37.191,28.616-32.869,80.268-32.663,82.456c0.2' +
      '31,2.681,2.022,5.04,4.608,5.964c0.588,0.164,14.39,5.033,33.308,5.033 c' +
      '21.354,0,40.271-5.909,56.37-17.618c35.072-25.661,34.074-75.314,34.033-' +
      '77.395C684.883,415.25,683.296,412.87,680.834,411.748z M660.314,460.444' +
      'c-9.753,0-17.728-7.906-17.728-17.591c0-9.794,7.975-17.618,17.728-17.61' +
      '8c9.739,0,17.618,7.824,17.618,17.618 C677.933,452.538,670.054,460.444,' +
      '660.314,460.444z',
      'M886.069,569.957c-21.791-6.751-43.225-11.244-64.058-14.062c15.785-54.7' +
      '64,14.376-120.708-16.866-201.488 c52.636-95.478,29.808-268.898,28.78-2' +
      '76.585c-1.259-9.547-7.387-17.755-16.143-21.722c-8.821-4.049-18.998-3.2' +
      '01-27.028,2.106 L618.513,171.904c-49.094-22.078-114.479-35.482-175.203' +
      '-35.482c-61.39,0-123.717,12.919-173.72,35.701L84.489,57.768 c-8.07-5.0' +
      '61-18.172-5.636-26.674-1.505c-8.563,4.049-14.534,12.147-15.812,21.558c' +
      '-0.958,7.195-22.461,171.341,36.296,277.051 C50.729,435.905,49.676,501.' +
      '57,65.407,556.36c-19.711,2.852-39.942,7.222-60.474,13.597c-3.7,1.148-5' +
      '.752,5.033-4.624,8.754 c1.177,3.722,5.171,5.802,8.775,4.598c20.552-6.3' +
      '68,40.858-10.629,60.651-13.316c4.507,12.878,9.924,25.162,16.189,36.857' +
      ' c-22.563,6.292-44.976,14.808-67.21,25.593c-3.475,1.696-4.925,5.854-3.' +
      '222,9.355c1.197,2.47,3.693,3.939,6.292,3.939 c1.033,0,2.079-0.219,3.05' +
      '7-0.711c22.577-10.93,45.352-19.41,68.284-25.546c5.752,9.494,12.044,18.' +
      '609,18.802,27.379 c-20.053,9.418-40.284,22.364-60.022,40.078c-2.873,2.' +
      '572-3.126,7.004-0.547,9.904c1.395,1.53,3.303,2.298,5.225,2.298 c1.668,' +
      '0,3.331-0.597,4.678-1.807c19.67-17.666,39.75-30.388,59.557-39.409c37.5' +
      '35,44.702,86.758,80.344,135.831,112.29 c38.574,25.113,114.108,67.244,1' +
      '86.66,67.244c57.195,0,132.142-26.592,190.96-67.792c42.351-29.717,93.30' +
      '3-65.486,132.875-113.062 c20.778,9.096,41.885,22.166,62.555,40.729c1.3' +
      '82,1.21,3.021,1.807,4.719,1.807c1.915,0,3.83-0.768,5.185-2.298 c2.585-' +
      '2.9,2.354-7.332-0.479-9.904c-20.737-18.596-42.021-32.008-63.046-41.516' +
      'c6.523-8.568,12.611-17.535,18.261-26.852 c24.116,6.196,48.081,14.951,7' +
      '1.813,26.455c0.984,0.492,2.023,0.711,3.063,0.711c2.571,0,5.089-1.471,6' +
      '.278-3.939 c1.71-3.502,0.231-7.659-3.215-9.355c-23.392-11.333-46.986-2' +
      '0.143-70.732-26.516c6.183-11.546,11.654-23.651,16.141-36.413 c20.915,2' +
      '.646,42.433,7.051,64.224,13.795c3.721,1.147,7.592-0.876,8.754-4.598C89' +
      '1.814,574.99,889.735,571.105,886.069,569.957z M764.589,307.953c-17.659' +
      '-18.33-35.895-31.407-41.296-22.597c-5.745,9.329,8.862,48.669,22.815,74' +
      '.057 c0.547,0.985,1.148,1.012,1.75,1.696c0.15,0.492,0,1.04,0.22,1.532c' +
      '7.004,16.715,12.134,32.336,16.47,47.491 c-19.767-13.732-56.534-28.726-' +
      '56.534-9.301c0.123,22.789,52.431,89.678,66.26,112.275c-1.888,13.713-5.' +
      '32,26.64-9.82,39.047 c-100.253,0.431-176.211,35.845-186.538,43.628c-3.' +
      '063,2.298-3.722,6.676-1.367,9.794c1.367,1.806,3.447,2.791,5.581,2.791 ' +
      'c1.478,0,2.954-0.438,4.199-1.423c9.15-6.854,79.638-38.67,172.298-40.51' +
      '7c-4.541,9.979-9.903,19.58-15.99,28.868 c-49.135-4.69-98.789,0.931-148' +
      '.524,17.119c-2.353,0.767-4.158,1.367-5.484,1.751c-3.707,1.039-5.842,4.' +
      '924-4.802,8.646 c1.025,3.721,4.925,5.745,8.632,4.814c1.478-0.383,3.461' +
      '-1.04,5.978-1.859c45.153-14.761,90.239-20.505,134.928-17.297 c-4.938,6' +
      '.564-10.163,13.021-15.799,19.313c-51.925-8.57-96.75,1.272-119.785,6.35' +
      '4l-4.542,0.984 c-3.774,0.82-6.183,4.541-5.36,8.316c0.807,3.774,4.649,6' +
      '.183,8.315,5.362l4.65-0.985c22.297-4.979,60.707-13.446,105.312-7.906 c' +
      '-28.876,29.32-64.756,56.315-104.067,83.906c-49.229,34.47-113.028,57.61' +
      '4-158.774,57.614 c-42.431,0-99.308-21.176-156.081-58.162c-39.238-25.54' +
      '5-76.39-52.034-106.373-82.777c46.241-6.545,86.271,2.202,109.3,7.277 l4' +
      '.712,1.033c3.715,0.819,7.518-1.588,8.317-5.362c0.82-3.775-1.587-7.496-' +
      '5.362-8.316l-4.649-1.04 c-23.556-5.144-69.995-15.312-123.492-5.636c-5.' +
      '554-6.319-10.738-12.856-15.621-19.581c45.851-3.769,92.14,1.807,138.511' +
      ',16.9 c2.511,0.82,4.515,1.478,5.964,1.859c3.611,0.875,7.605-1.148,8.64' +
      '6-4.814c1.06-3.721-1.094-7.605-4.822-8.646 c-1.306-0.384-3.146-0.984-5' +
      '.437-1.751c-50.906-16.552-101.654-22.092-151.855-16.824c-5.875-9.315-1' +
      '1.073-19.041-15.512-29.231 c94.042,1.245,165.944,33.664,175.185,40.585' +
      'c1.266,0.985,2.715,1.423,4.192,1.423c2.134,0,4.233-0.984,5.608-2.791 c' +
      '2.324-3.118,1.695-7.496-1.424-9.794c-10.464-7.845-87.681-43.812-189.16' +
      '4-43.642c-5.307-15.115-9.096-31.146-10.847-48.443 c19.144-28.069,60.04' +
      '3-82.757,60.132-102.865c0-17.919-31.243-6.511-51.624,6.155c3.611-14.55' +
      '4,7.934-29.574,13.788-45.522 c0.41-1.095,0.137-2.271,0.41-3.394c13.734' +
      '-25.415,27.823-63.551,22.153-72.716c-5.308-8.646-22.946,3.83-40.325,21' +
      '.612 c-23.637-57.369-25.518-131.098-23.548-177.414l159.192,98.351c8.34' +
      '5,5.253,18.904,5.554,27.687,1.012 c5.581-2.927,12.146-5.225,18.241-7.8' +
      '52c12.29,20.163,34.312,49.435,41.781,58.053c13.042,15.074,46.009-60.76' +
      '1,34.251-80.103 c9.85-1.724,19.615-3.365,29.628-4.377c-14.089,34.005,1' +
      '2.394,115.257,30.23,98.405c16.432-15.539,55.184-70.528,58.098-97.038 c' +
      '13.911,1.806,27.81,4.11,41.2,7.195c-7.975,25.88,0.726,69.871-0.149,84.' +
      '48c-0.931,15.102,55.303-25.716,77.858-57.8 c8.029,2.626,16.784,2.346,2' +
      '3.965-2.414l146.474-96.709C785.504,183.23,783.971,257.15,764.589,307.9' +
      '53z',
    ];
    return html`
      <svg viewBox="0 0 900 900"
          id="cat"
          license="http://creativecommons.org/licenses/by/3.0/"
          author="https://www.flaticon.com/authors/tutsplus">
        ${PATHS.map(data => svg`<path d="${data}"/>`)}
      </svg>
    `;
  }

  render() {
    const allTriaged = this.showingTriaged ? (this.alertGroups.length === 0) :
      ((this.alertGroups || []).filter(group =>
        group.alerts.length > group.triaged.count).length === 0);
    const bodies = (this.alertGroups || []).map((alertGroup, alertGroupIndex) =>
      this.renderGroup(alertGroup, alertGroupIndex));

    return allTriaged ? html`
      <center>
        All alerts triaged! ${this.renderCat()}
      </center>
    ` : html`
      <div id="scroll">
        <table ?placeholder="${this.areAlertGroupsPlaceholders}">
          <thead>
            <tr>
              <th>
                <column-head
                     name="count"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Count
                </column-head>
              </th>

              ${this.showTriagedColumn ? html`
                <th>
                  <column-head
                       name="triaged"
                      .sortColumn="${this.sortColumn}"
                      .sortDescending="${this.sortDescending}"
                      ?disabled="${this.areAlertGroupsPlaceholders}"
                      @click="${this.onSort_}">
                    Triaged
                  </column-head>
                </th>
              ` : ''}

              <th class="checkbox">
                <cp-checkbox
                    ?checked="${this.selectedAlertsCount > 0}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @change="${this.onSelectAll_}">
                </cp-checkbox>
              </th>

              ${this.showBugColumn ? html`
                <th>
                  <column-head
                       name="bugId"
                      .sortColumn="${this.sortColumn}"
                      .sortDescending="${this.sortDescending}"
                      ?disabled="${this.areAlertGroupsPlaceholders}"
                      @click="${this.onSort_}">
                    Bug
                  </column-head>
                </th>
              ` : ''}

              <th>
                <column-head
                     name="startRevision"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Revisions
                </column-head>
              </th>

              <th>
                <column-head
                     name="suite"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Suite
                </column-head>
              </th>

              <th>
                <column-head
                    name="measurement"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Measurement
                </column-head>
              </th>

              ${this.showMasterColumn ? html`
                <th>
                  <column-head
                       name="master"
                      .sortColumn="${this.sortColumn}"
                      .sortDescending="${this.sortDescending}"
                      ?disabled="${this.areAlertGroupsPlaceholders}"
                      @click="${this.onSort_}">
                    Master
                  </column-head>
                </th>
              ` : ''}

              <th>
                <column-head
                     name="bot"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Bot
                </column-head>
              </th>

              ${this.showCaseColumn ? html`
                <th>
                  <column-head
                       name="case"
                      .sortColumn="${this.sortColumn}"
                      .sortDescending="${this.sortDescending}"
                      ?disabled="${this.areAlertGroupsPlaceholders}"
                      @click="${this.onSort_}">
                    Case
                  </column-head>
                </th>
              ` : ''}

              <th>
                <column-head
                     name="deltaValue"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Delta
                </column-head>
              </th>

              <th>
                <column-head
                     name="percentDeltaValue"
                    .sortColumn="${this.sortColumn}"
                    .sortDescending="${this.sortDescending}"
                    ?disabled="${this.areAlertGroupsPlaceholders}"
                    @click="${this.onSort_}">
                  Delta %
                </column-head>
              </th>
            </tr>
          </thead>

          ${bodies}
        </table>
      </div>
    `;
  }

  renderGroup(alertGroup, alertGroupIndex) {
    const expandedGroup = alertGroup.isExpanded ||
      alertGroup.triaged.isExpanded;
    const rows = alertGroup.alerts.map((alert, alertIndex) =>
      this.renderAlert(alertGroup, alertGroupIndex, alert, alertIndex));
    return html`
      <tbody ?expandedGroup="${expandedGroup}">
        ${rows}
      </tbody>
    `;
  }

  renderAlert(alertGroup, alertGroupIndex, alert, alertIndex) {
    if (!AlertsTable.shouldDisplayAlert(
        this.areAlertGroupsPlaceholders, this.showingTriaged, alertGroup,
        alertIndex, alertGroup.triaged.isExpanded)) {
      return '';
    }

    // Most monitored timeseries on ChromiumPerf bots use revisions that are
    // supported by test-results.appspot.com.
    // TODO(benjhayden) Support revision range links more generally.
    const alertRevisionHref = (alert.master !== 'ChromiumPerf') ? '' :
      `http://test-results.appspot.com/revision_range?start=${alert.startRevision}&end=${alert.endRevision}&n=1000`;

    const alertRevisionString = (alert.startRevision === alert.endRevision) ?
      alert.startRevision : (alert.startRevision + '-' + alert.endRevision);

    const shouldDisplayExpandGroupButton =
      AlertsTable.shouldDisplayExpandGroupButton(
          alertGroup, alertIndex, this.showingTriaged);

    const expandGroupButtonLabel = this.showingTriaged ?
      alertGroup.alerts.length :
      (alertGroup.alerts.length - alertGroup.triaged.count);

    const shouldDisplayExpandTriagedButton =
      AlertsTable.shouldDisplayExpandTriagedButton(
          this.showingTriaged, alertGroup, alertIndex);

    const shouldDisplaySelectedCount = (this.showingTriaged) ?
      (alertIndex === 0) :
      (alertIndex === alertGroup.alerts.findIndex(a => !a.bugId));

    const expandTriagedStatePath =
      `${this.statePath}.alertGroups.${alertGroupIndex}.triaged`;

    const onRowClick = event =>
      this.onRowClick_(event, alertGroupIndex, alertIndex);

    let bugLink = '';
    if (this.showBugColumn) {
      if (this.areAlertGroupsPlaceholders) {
        bugLink = alert.bugId;
      } else if (alert.bugId < 0) {
        bugLink = 'Ignored';
      } else if (alert.bugId > 0) {
        bugLink = html`
          <a href="${crbug(alert.bugId)}" target="_blank">${alert.bugId}</a>
        `;
      }
    }

    return html`
      <tr ?untriaged="${!alert.bugId}" @click="${onRowClick}">
        <td>
          ${shouldDisplayExpandGroupButton ? html`
            <expand-button
                .statePath="${this.statePath}.alertGroups.${alertGroupIndex}">
              ${expandGroupButtonLabel}
            </expand-button>
          ` : ''}
        </td>

        ${this.showTriagedColumn ? html`
          <td>
            ${shouldDisplayExpandTriagedButton ? html`
              <expand-button .statePath="${expandTriagedStatePath}">
                ${alertGroup.triaged.count}
              </expand-button>
            ` : ''}
          </td>
        ` : ''}

        <td>
          <cp-checkbox
              ?checked="${alert.isSelected}"
              ?disabled="${this.areAlertGroupsPlaceholders}"
              @change="${event =>
    this.onSelect_(event, alertGroupIndex, alertIndex)}">
            ${shouldDisplaySelectedCount ? this.selectedCount_(alertGroup) : ''}
          </cp-checkbox>
        </td>

        ${this.showBugColumn ? html`
          <td>${bugLink}</td>
        ` : ''}

        <td>
          ${alertRevisionHref ? html`
            <a href="${alertRevisionHref}" target="_blank">
              ${alertRevisionString}
            </a>
          ` : html`
            ${alertRevisionString}
          `}
        </td>

        <td style="color: ${alert.color};">
          ${breakWords(alert.suite)}
        </td>
        <td style="color: ${alert.color};">
          ${breakWords(alert.measurement)}
        </td>

        ${this.showMasterColumn ? html`
          <td style="color: ${alert.color};">
            ${alert.master}
          </td>
        ` : ''}

        <td style="color: ${alert.color};">
          ${alert.bot}
        </td>

        ${this.showCaseColumn ? html`
          <td style="color: ${alert.color};">
            ${breakWords(alert.case)}
          </td>
        ` : ''}

        <td>
          <scalar-span
              .value="${alert.deltaValue}"
              .unit="${alert.deltaUnit}">
          </scalar-span>
        </td>

        <td>
          <scalar-span
              .value="${alert.percentDeltaValue}"
              .unit="${alert.percentDeltaUnit}"
              .maximumFractionDigits="1">
          </scalar-span>
        </td>
      </tr>
    `;
  }

  firstUpdated() {
    this.scrollIntoView(true);
  }

  stateChanged(rootState) {
    super.stateChanged(rootState);
    this.areAlertGroupsPlaceholders = (this.alertGroups ===
      AlertsTable.placeholderAlertGroups());
  }

  selectedCount_(alertGroup) {
    if (!alertGroup) return '';
    if (alertGroup.alerts.length === 1) return '';
    let count = 0;
    for (const alert of alertGroup.alerts) {
      if (alert.isSelected) ++count;
    }
    if (count === 0) return '';
    return `${count}/${alertGroup.alerts.length}`;
  }

  async onSelectAll_(event) {
    event.target.checked = !event.target.checked;
    await STORE.dispatch({
      type: AlertsTable.reducers.selectAllAlerts.name,
      statePath: this.statePath,
    });
    this.dispatchEvent(new CustomEvent('selected', {
      bubbles: true,
      composed: true,
    }));
  }

  async onSelect_(event, alertGroupIndex, alertIndex) {
    let shiftKey = false;
    if (event.detail && event.detail.event &&
        (event.detail.event.shiftKey ||
          (event.detail.event.detail && event.detail.event.detail.shiftKey))) {
      shiftKey = true;
    }
    await STORE.dispatch({
      type: AlertsTable.reducers.selectAlert.name,
      statePath: this.statePath,
      alertGroupIndex,
      alertIndex,
      shiftKey,
    });
    this.dispatchEvent(new CustomEvent('selected', {
      bubbles: true,
      composed: true,
    }));
  }

  async onSort_(event) {
    await STORE.dispatch({
      type: AlertsTable.reducers.sort.name,
      statePath: this.statePath,
      sortColumn: event.target.name,
    });
    this.dispatchEvent(new CustomEvent('sort', {
      bubbles: true,
      composed: true,
    }));
  }

  async onRowClick_(event, alertGroupIndex, alertIndex) {
    if (event.target.tagName !== 'TD') return;
    this.dispatchEvent(new CustomEvent('alert-click', {
      bubbles: true,
      composed: true,
      detail: {
        alertGroupIndex,
        alertIndex,
      },
    }));
  }

  static getSelectedAlerts(alertGroups) {
    const selectedAlerts = [];
    for (const alertGroup of alertGroups) {
      for (const alert of alertGroup.alerts) {
        if (alert.isSelected) {
          selectedAlerts.push(alert);
        }
      }
    }
    return selectedAlerts;
  }
}

AlertsTable.shouldDisplayAlert = (
    areAlertGroupsPlaceholders, showingTriaged, alertGroup, alertIndex,
    triagedExpanded) => {
  if (areAlertGroupsPlaceholders) return true;
  if (showingTriaged) return alertGroup.isExpanded || (alertIndex === 0);

  if (!alertGroup.alerts[alertIndex]) return false;
  const isTriaged = alertGroup.alerts[alertIndex].bugId;
  const firstUntriagedIndex = alertGroup.alerts.findIndex(a => !a.bugId);
  if (alertGroup.isExpanded) {
    return !isTriaged || triagedExpanded || (
      alertIndex === firstUntriagedIndex);
  }
  if (isTriaged) return triagedExpanded;
  return alertIndex === firstUntriagedIndex;
};

AlertsTable.shouldDisplayExpandGroupButton = (
    alertGroup, alertIndex, showingTriaged) => {
  if (showingTriaged) {
    return (alertIndex === 0) && alertGroup.alerts.length > 1;
  }
  return (alertIndex === alertGroup.alerts.findIndex(a => !a.bugId)) && (
    alertGroup.alerts.length > (1 + alertGroup.triaged.count));
};

AlertsTable.shouldDisplayExpandTriagedButton = (
    showingTriaged, alertGroup, alertIndex) => {
  if (showingTriaged || (alertGroup.triaged.count === 0)) return false;
  return alertIndex === alertGroup.alerts.findIndex(a => !a.bugId);
};

AlertsTable.compareAlerts = (alertA, alertB, sortColumn) => {
  let valueA = alertA[sortColumn];
  let valueB = alertB[sortColumn];
  if (sortColumn === 'percentDeltaValue') {
    valueA = Math.abs(valueA);
    valueB = Math.abs(valueB);
  }
  if (typeof valueA === 'string') return valueA.localeCompare(valueB);
  return valueA - valueB;
};

AlertsTable.sortGroups = (
    alertGroups, sortColumn, sortDescending, showingTriaged) => {
  const factor = sortDescending ? -1 : 1;
  if (sortColumn === 'count') {
    alertGroups = [...alertGroups];
    // See AlertsTable.getExpandGroupButtonLabel_.
    if (showingTriaged) {
      alertGroups.sort((groupA, groupB) =>
        factor * (groupA.alerts.length - groupB.alerts.length));
    } else {
      alertGroups.sort((groupA, groupB) =>
        factor * ((groupA.alerts.length - groupA.triaged.count) -
          (groupB.alerts.length - groupB.triaged.count)));
    }
  } else if (sortColumn === 'triaged') {
    alertGroups = [...alertGroups];
    alertGroups.sort((groupA, groupB) =>
      factor * (groupA.triaged.count - groupB.triaged.count));
  } else {
    alertGroups = alertGroups.map(group => {
      const alerts = Array.from(group.alerts);
      alerts.sort((alertA, alertB) => factor * AlertsTable.compareAlerts(
          alertA, alertB, sortColumn));
      return {
        ...group,
        alerts,
      };
    });
    alertGroups.sort((groupA, groupB) => factor * AlertsTable.compareAlerts(
        groupA.alerts[0], groupB.alerts[0], sortColumn));
  }
  return alertGroups;
};

AlertsTable.DASHES = '-'.repeat(5);
const PLACEHOLDER_ALERT_GROUPS = [];
AlertsTable.placeholderAlertGroups = () => {
  if (PLACEHOLDER_ALERT_GROUPS.length) return PLACEHOLDER_ALERT_GROUPS;
  for (let i = 0; i < 5; ++i) {
    PLACEHOLDER_ALERT_GROUPS.push({
      isSelected: false,
      triaged: {
        count: 0,
        isExpanded: false,
      },
      alerts: [
        {
          bugId: AlertsTable.DASHES,
          startRevision: AlertsTable.DASHES,
          endRevision: AlertsTable.DASHES,
          suite: AlertsTable.DASHES,
          measurement: AlertsTable.DASHES,
          master: AlertsTable.DASHES,
          bot: AlertsTable.DASHES,
          case: AlertsTable.DASHES,
          deltaValue: 0,
          deltaUnit: tr.b.Unit.byName.countDelta_biggerIsBetter,
          percentDeltaValue: 0,
          percentDeltaUnit:
            tr.b.Unit.byName.normalizedPercentageDelta_biggerIsBetter,
        },
      ],
    });
  }
  return PLACEHOLDER_ALERT_GROUPS;
};

AlertsTable.reducers = {
  sort: (state, action, rootState) => {
    if (!state ||
        (state.alertGroups === AlertsTable.placeholderAlertGroups())) {
      return state;
    }
    const sortDescending = state.sortDescending ^ (state.sortColumn ===
        action.sortColumn);
    const alertGroups = AlertsTable.sortGroups(
        state.alertGroups, action.sortColumn, sortDescending);
    return {
      ...state,
      sortColumn: action.sortColumn,
      sortDescending,
      alertGroups,
    };
  },

  selectAlert: (state, {shiftKey, alertIndex, alertGroupIndex}, rootState) => {
    let alertGroups = state.alertGroups;
    const alertGroup = alertGroups[alertGroupIndex];
    let alerts = alertGroup.alerts;
    const alert = alerts[alertIndex];
    const isSelected = !alert.isSelected;

    if (shiftKey) {
      // [De]select all alerts between previous selected alert and |alert|.
      // Deep-copy alerts so that we can freely modify them.
      // Copy references to individual alerts out of their groups to reflect
      // the flat list of checkboxes that the user sees.
      const flatList = [];
      alertGroups = alertGroups.map(g => {
        return {
          ...g,
          alerts: g.alerts.map(a => {
            const clone = {...a};
            flatList.push(clone);
            return clone;
          }),
        };
      });
      // Find the indices of the previous selected alert and |alert| in
      // flatList.
      const indices = new tr.b.math.Range();
      const keys = [state.previousSelectedAlertKey, alert.key];
      for (let i = 0; i < flatList.length; ++i) {
        if (keys.includes(flatList[i].key)) indices.addValue(i);
      }
      if (state.previousSelectedAlertKey === undefined) indices.addValue(0);
      // Set isSelected for all alerts that appear in the table between the
      // previous selected alert and |alert|.
      for (let i = indices.min; i <= indices.max; ++i) {
        flatList[i].isSelected = isSelected;
      }
    } else {
      let toggleAll = false;
      if (!alertGroup.isExpanded) {
        if (state.showingTriaged) {
          toggleAll = alertIndex === 0;
        } else {
          toggleAll = alertIndex === alertGroup.alerts.findIndex(
              a => !a.bugId);
        }
      }
      if (toggleAll) {
        alerts = alerts.map(alert => {
          if (!state.showingTriaged && alert.bugId) return alert;
          return {
            ...alert,
            isSelected,
          };
        });
      } else {
        // Only toggle this alert.
        alerts = setImmutable(
            alerts, `${alertIndex}.isSelected`, isSelected);
      }

      alertGroups = setImmutable(
          state.alertGroups, `${alertGroupIndex}.alerts`, alerts);
    }

    const selectedAlertsCount = AlertsTable.getSelectedAlerts(
        alertGroups).length;
    return {
      ...state,
      alertGroups,
      previousSelectedAlertKey: alert.key,
      selectedAlertsCount,
    };
  },

  selectAllAlerts: (state, action, rootState) => {
    if (!state) return state;
    const select = (state.selectedAlertsCount === 0);
    const alertGroups = state.alertGroups.map(alertGroup => {
      return {
        ...alertGroup,
        alerts: alertGroup.alerts.map(alert => {
          return {
            ...alert,
            isSelected: select,
          };
        }),
      };
    });
    return {
      ...state,
      alertGroups,
      selectedAlertsCount: AlertsTable.getSelectedAlerts(alertGroups).length,
    };
  },
};

ElementBase.register(AlertsTable);
