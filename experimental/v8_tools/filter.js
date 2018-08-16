'use strict';
const MiB = 1024 * 1024;
const bus = new Vue();
Vue.component('v-select', VueSelect.VueSelect);


//  Register the table component for displaying data.
//  This is a child for the app Vue instance, so it might
//  access some of the app's fields.
Vue.component('data-table', {
  template: '#table-template',
  props: {
    data: Array,
    columns: Array,
    filterKey: String
  },
  data() {
    const sort = {};
    this.columns.forEach(function(key) {
      sort[key] = 1;
    });
    return {
      sortKey: '',
      sortOrders: sort,
      openedMetric: [],
      openedStory: [],
      storiesEntries: null,
      diagnosticsEntries: null,
      metric: null,
      story: null,
      diagnostic: null,
      selected_diagnostics: [],
      plot_kinds: ['Cumulative frequency plot', 'Dot plot'],
      chosen_plot: ''
    };
  },
  computed: {
    //  Filter data from one column.
    filteredData() {
      const sortKey = this.sortKey;
      const filterKey = this.filterKey && this.filterKey.toLowerCase();
      const order = this.sortOrders[sortKey] || 1;
      let data = this.data;
      if (filterKey) {
        data = data.filter(function(row) {
          return Object.keys(row).some(function(key) {
            return String(row[key]).toLowerCase().indexOf(filterKey) > -1;
          });
        });
      }
      if (sortKey) {
        data = data.slice().sort(function(a, b) {
          a = a[sortKey];
          b = b[sortKey];
          return (a === b ? 0 : a > b ? 1 : -1) * order;
        });
      }
      return data;
    },

    //  All sub-diagnostics must be visible just after the user
    //  has already chosen a specific diagnostic and all the
    //  options for that one are now available.
    seen_diagnostics() {
      if (this.diagnostics_options !== null &&
        this.diagnostics_options !== undefined &&
        this.diagnostics_options.length !== 0) {
        return this.diagnostics_options.length > 0 ? true : false;
      }
    },

    //  All the options for plots must be visible after the user
    //  has already chosen all the necessary items for displaying
    //  a plot.
    seen_plot() {
      if (this.selected_diagnostics !== null &&
        this.selected_diagnostics !== undefined &&
        this.selected_diagnostics.length !== 0) {
        return this.selected_diagnostics.length > 0 ? true : false;
      }
    },

    //  Compute all the options for sub-diagnostics after the user
    //  has already chosen a specific diagnostic.
    //  Depending on the GUID of that diagnostic, the value can be
    //  a string, a number or undefined.
    diagnostics_options() {
      if (this.story !== null &&
      this.metric !== null &&
      this.diagnostic !== null) {
        const sampleArr = this.$parent.sampleArr;
        const guidValue = this.$parent.guidValue;
        const result = sampleArr
            .filter(value => value.name === this.metric.metric &&
                  guidValue
                      .get(value.diagnostics.stories)[0] ===
                      this.story.story);
        const content = [];
        for (const val of result) {
          const diagnosticItem = guidValue.get(
              val.diagnostics[this.diagnostic]);
          if (diagnosticItem === undefined) {
            continue;
          }
          let currentDiagnostic = '';
          if (typeof diagnosticItem === 'number') {
            currentDiagnostic = diagnosticItem.toString();
          } else {
            currentDiagnostic = diagnosticItem[0];
            if (typeof currentDiagnostic === 'number') {
              currentDiagnostic = currentDiagnostic.toString();
            }
          }
          content.push(currentDiagnostic);
        }
        return _.uniq(content);
      }
      return undefined;
    }
  },
  //  Capitalize the objects field names.
  filters: {
    capitalize(str) {
      return str.charAt(0).toUpperCase() + str.slice(1);
    }
  },

  methods: {
    //  Sort by key where the key is a title head in table.
    sortBy(key) {
      this.sortKey = key;
      this.sortOrders[key] = this.sortOrders[key] * -1;
    },

    //  Remove all the selected items from the array.
    //  Especially for the cases when the user changes the mind and select
    //  another high level diagnostic and the selected sub-diagnostics
    //  will not be usefull anymore.
    empty() {
      this.selected_diagnostics = [];
    },

    //  This method will be called when the user clicks a specific
    //  'row in table' = 'metric' and we have to provide the stories for that.
    //  Also all the previous choices must be removed.
    toggleMetric(entry) {
      const index = this.openedMetric.indexOf(entry.id);
      if (index > -1) {
        this.openedMetric.splice(index, 1);
      } else {
        this.openedMetric.push(entry.id);
      }
      const sampleArr = this.$parent.sampleArr;
      const guidValue = this.$parent.guidValue;
      const storiesEntries = [];

      const storiesAverage = new Map();
      for (const e of sampleArr) {
        let nameOfStory = guidValue.get(e.diagnostics.stories);
        if (nameOfStory === undefined) {
          continue;
        }
        if (typeof nameOfStory !== 'number') {
          nameOfStory = nameOfStory[0];
        }
        if (storiesAverage.has(nameOfStory)) {
          const current = storiesAverage.get(nameOfStory);
          current.push(average(e.sampleValues));
          storiesAverage.set(nameOfStory, current);
        } else {
          const current = [average(e.sampleValues)];
          storiesAverage.set(nameOfStory, current);
        }
      }
      for (const [key, value] of storiesAverage) {
        storiesEntries.push(
            new StoryRow(key, average(value))
        );
      }

      this.storiesEntries = storiesEntries;
      this.metric = entry;
      this.diagnostic = null;
      this.empty();
    },

    //  This method will be called when the user clicks a specific
    //  story row and we have to compute all the available diagnostics.
    //  Also all the previous choices regarding a diagnostic must be removed.
    toggleStory(story) {
      const index = this.openedStory.indexOf(story.story);
      if (index > -1) {
        this.openedStory.splice(index, 1);
      } else {
        this.openedStory.push(story.story);
      }
      const sampleArr = this.$parent.sampleArr;
      const guidValue = this.$parent.guidValue;
      const result = sampleArr
          .filter(value => value.name === this.metric.metric &&
              guidValue
                  .get(value.diagnostics.stories)[0] ===
                  story.story);
      const allDiagnostic = [];
      result.map(val => allDiagnostic.push(Object.keys(val.diagnostics)));
      this.diagnosticsEntries = _.union.apply(this, allDiagnostic);
      this.story = story;
      this.diagnostic = null;
      this.empty();
    },

    createPlot() {
      if (this.selected_diagnostics !== null &&
        this.selected_diagnostics.length !== 0 &&
        this.diagnostic !== null) {
        app.plotDiagnostics(this.metric.metric,
            this.story.story, this.diagnostic,
            this.selected_diagnostics,
            this.chosen_plot);
      }
    }
  },

  watch: {
    //  Whenever a new diagnostic is chosen or removed, the graph
    //  is replotted because these are displayed in the same plot
    //  by comparison and it should be updated.
    selected_diagnostics() {
      this.createPlot();
    },

    //  Whenever the chosen plot is changed by the user it has to
    //  be created another type of plot with the same specifications.
    chosen_plot() {
      this.createPlot();
    },

    //  Whenever the top level diagnostic is changed all the previous
    //  selected sub-diagnostics have to be removed. Otherwise the old
    //  selections will be displayed. Also the plot is displayed with
    //  values for all available sub-diagnostics.
    diagnostic() {
      this.empty();
      app.plotDefaultByDiagnostic(this.metric.metric,
          this.story.story, this.diagnostic);
    }
  }
});

//  Vue component for drop-down menu; here the metrics,
//  stories and diagnostics are chosen through selection.
const app = new Vue({
  el: '#app',
  data: {
    sampleArr: [],
    guidValue: null,
    selected_metric: null,
    selected_story: null,
    selected_diagnostic: null,
    graph: null,
    searchQuery: '',
    gridColumns: ['id', 'metric', 'averageSampleValues'],
    gridData: []
  },

  methods: {
    //  Draw a cumulative frequency plot depending on the target value.
    //  This is mainly for results from the drop-down menu.
    plotCumulativeFrequency() {
      this.graph.xAxis('Data Points')
          .yAxis('Memory used (MiB)')
          .title(this.selected_story)
          .addData(JSON.parse(JSON.stringify((this.target))))
          .plotCumulativeFrequency();
    },

    //  Draw a dot plot depending on the target value.
    //  This is mainly for results from the table.
    plotDotPlot(target, story) {
      this.graph
          .xAxis('Memory used (MiB)')
          .title(story)
          .addData(JSON.parse(JSON.stringify(target)))
          .plotDot();
    },

    //  Draw a cumulative frequency plot depending on the target value.
    //  This is mainly for the results from the table.
    plotCumulativeFrequencyPlot(target, story) {
      this.graph.xAxis('Data Points')
          .yAxis('Memory used (MiB)')
          .title(story)
          .addData(JSON.parse(JSON.stringify(target)))
          .plotCumulativeFrequency();
    },

    //  Draw a plot by default with all the sub-diagnostics
    //  in the same plot;
    plotDefaultByDiagnostic(metric, story, diagnostic) {
      const result = this.sampleArr
          .filter(value => value.name === metric &&
              this.guidValue
                  .get(value.diagnostics.stories)[0] ===
                  story);

      const content = new Map();
      for (const val of result) {
        const diagnosticItem = this.guidValue.get(
            val.diagnostics[diagnostic]);
        if (diagnosticItem === undefined) {
          continue;
        }
        let currentDiagnostic = '';
        if (typeof diagnosticItem === 'number') {
          currentDiagnostic = diagnosticItem;
        } else {
          currentDiagnostic = diagnosticItem[0];
        }
        if (content.has(currentDiagnostic)) {
          const aux = content.get(currentDiagnostic);
          content.set(currentDiagnostic, aux.concat(val.sampleValues));
        } else {
          content.set(currentDiagnostic, val.sampleValues);
        }
      }
      const contentKeys = [];
      const contentVal = [];
      for (const [key, value] of content.entries()) {
        value.map(value => +((value / MiB).toFixed(5)));
        contentKeys.push(key);
        contentVal.push(value);
      }
      const obj = _.object(contentKeys, contentVal);
      if (this.graph === null) {
        this.graph = new GraphData();
        this.plotCumulativeFrequencyPlot(obj, story);
      } else {
        this.graph.plotter_.remove();
        this.graph = new GraphData();
        this.plotCumulativeFrequencyPlot(obj, story);
      }
    },
    //  Draw a plot depending on the target value which is made
    //  of a metric, a story, a diagnostic and a couple of sub-diagnostics
    //  and the chosen type of plot. All are chosen from the table.
    plotDiagnostics(metric, story, diagnostic,
        diagnostics, chosenPlot) {
      const target = this.targetForMultipleDiagnostics(metric, story,
          diagnostic, diagnostics);
      if (chosenPlot === 'Dot plot') {
        if (this.graph === null) {
          this.graph = new GraphData();
          this.plotDotPlot(target, story);
        } else {
          this.graph.plotter_.remove();
          this.graph = new GraphData();
          this.plotDotPlot(target, story);
        }
      } else {
        if (this.graph === null) {
          this.graph = new GraphData();
          this.plotCumulativeFrequencyPlot(target, story);
        } else {
          this.graph.plotter_.remove();
          this.graph = new GraphData();
          this.plotCumulativeFrequencyPlot(target, story);
        }
      }
    },

    //  Compute the target when the metric, story, diagnostics and
    //  sub-diagnostics come from the table, not from the drop-down menu.
    //  It should be the same for both components but for now they should
    //  be divided.
    targetForMultipleDiagnostics(metric, story, diagnostic, diagnostics) {
      if (metric !== null && story !== null &&
        diagnostic !== null && diagnostics !== null) {
        const result = this.sampleArr
            .filter(value => value.name === metric &&
                    this.guidValue
                        .get(value.diagnostics.stories)[0] ===
                        story);

        const content = new Map();
        for (const val of result) {
          const diagnosticItem = this.guidValue.get(
              val.diagnostics[diagnostic]);
          if (diagnosticItem === undefined) {
            continue;
          }
          let currentDiagnostic = '';
          if (typeof diagnosticItem === 'number') {
            currentDiagnostic = diagnosticItem;
          } else {
            currentDiagnostic = diagnosticItem[0];
          }
          if (content.has(currentDiagnostic)) {
            const aux = content.get(currentDiagnostic);
            content.set(currentDiagnostic, aux.concat(val.sampleValues));
          } else {
            content.set(currentDiagnostic, val.sampleValues);
          }
        }

        const contentKeys = [];
        const contentVal = [];
        for (const [key, value] of content.entries()) {
          if (diagnostics.includes(key.toString())) {
            value.map(value => +((value / MiB).toFixed(5)));
            contentKeys.push(key);
            contentVal.push(value);
          }
        }
        const obj = _.object(contentKeys, contentVal);
        return obj;
      }
      return undefined;
    }
  },

  computed: {
    seen() {
      return this.sampleArr.length > 0 ? true : false;
    },

    seen_stories() {
      if (this.stories !== null && this.stories !== undefined) {
        return this.stories.length > 0 ? true : false;
      }
    },

    seen_diagnostics() {
      if (this.diagnostics !== null && this.diagnostics !== undefined) {
        return this.diagnostics.length > 0 ? true : false;
      }
    },

    //  Compute the metrics for the drop-down menu;
    //  The user will chose one of them.
    metrics() {
      const metricsNames = [];
      this.sampleArr.forEach(el => metricsNames.push(el.name));
      return _.uniq(metricsNames);
    },

    //  Compute the stories depending on the chosen metric.
    //  The user should chose one of them.
    stories() {
      const reqMetrics = this.sampleArr
          .filter(elem => elem.name === this.selected_metric);
      const storiesByGuid = [];
      for (const elem of reqMetrics) {
        let storyName = this.guidValue.get(elem.diagnostics.stories);
        if (storyName === undefined) {
          continue;
        }
        if (typeof storyName !== 'number') {
          storyName = storyName[0];
        }
        storiesByGuid.push(storyName);
      }
      return Array.from(new Set(storiesByGuid));
    },

    //  Compute all diagnostic elements; the final result will actually
    //  depend on the metric, the story and this diagnostic.
    diagnostics() {
      if (this.selected_story !== null && this.selected_metric !== null) {
        const result = this.sampleArr
            .filter(value => value.name === this.selected_metric &&
                    this.guidValue
                        .get(value.diagnostics.stories)[0] ===
                        this.selected_story);
        const allDiagnostic = [];
        result.map(val => allDiagnostic.push(Object.keys(val.diagnostics)));
        return _.union.apply(this, allDiagnostic);
      }
    },

    //  Compute the final result with the chosen metric, story and diagnostics.
    //  These are chosen from the drop-down menu.
    target() {
      if (this.selected_story !== null &&
        this.selected_metric !== null &&
        this.selected_diagnostic !== null) {
        const result = this.sampleArr
            .filter(value => value.name === this.selected_metric &&
                    this.guidValue
                        .get(value.diagnostics.stories)[0] ===
                        this.selected_story);

        const content = new Map();
        for (const val of result) {
          const diagnosticItem = this.guidValue.get(
              val.diagnostics[this.selected_diagnostic]);
          if (diagnosticItem === undefined) {
            continue;
          }
          let currentDiagnostic = '';
          if (typeof diagnosticItem === 'number') {
            currentDiagnostic = diagnosticItem;
          } else {
            currentDiagnostic = diagnosticItem[0];
          }
          if (content.has(currentDiagnostic)) {
            const aux = content.get(currentDiagnostic);
            content.set(currentDiagnostic, aux.concat(val.sampleValues));
          } else {
            content.set(currentDiagnostic, val.sampleValues);
          }
        }

        const contentKeys = [];
        const contentVal = [];
        for (const [key, value] of content.entries()) {
          value.map(value => +((value / MiB).toFixed(5)));
          contentKeys.push(key);
          contentVal.push(value);
        }
        const obj = _.object(contentKeys, contentVal);
        return obj;
      }
      return undefined;
    }
  },

  watch: {
    //  Whenever a new metric/ story/ diagnostic is chosen
    //  this function will run for drawing a new type of plot.
    //  These items are chosen from the drop-down menu.
    target() {
      if (this.graph === null) {
        this.graph = new GraphData();
        this.plotCumulativeFrequency();
      } else {
        this.graph.plotter_.remove();
        this.graph = new GraphData();
        this.plotCumulativeFrequency();
      }
    }
  }
});

//  A row from the default table.
class TableRow {
  constructor(id, metric, averageSampleValues) {
    this.id = id;
    this.metric = metric;
    this.averageSampleValues = averageSampleValues;
  }
}

//  A row after expanding a specific metric. This includes
//  all the stories from that metric plus the sample values
//  in the initial form, not the average.
class StoryRow {
  constructor(story, sample) {
    this.story = story;
    this.sample = sample;
  }
}

function average(arr) {
  return _.reduce(arr, function(memo, num) {
    return memo + num;
  }, 0) / arr.length;
}

//   Load the content of the file and further display the data.
function readSingleFile(e) {
  const file = e.target.files[0];
  if (!file) {
    return;
  }
  //  Extract data from file and distribute it in some relevant structures:
  //  results for all guid-related( for now they are not
  //  divided in 3 parts depending on the type ) and
  //  all results with sample-value-related and
  //  map guid to value within the same structure
  const reader = new FileReader();
  reader.onload = function(e) {
    const contents = extractData(e.target.result);
    const sampleArr = contents.sampleValueArray;
    const guidValueInfo = contents.guidValueInfo;
    const metricAverage = new Map();
    for (const e of sampleArr) {
      if (metricAverage.has(e.name)) {
        const aux = metricAverage.get(e.name);
        aux.push(average(e.sampleValues));
        metricAverage.set(e.name, aux);
      } else {
        metricAverage.set(e.name, [average(e.sampleValues)]);
      }
    }

    //  The content for the default table: with name
    //  of the mtric, the average value of the sample values
    //  plus an id. The latest is used to expand the row.
    // It may disappear later.
    const tableElems = [];
    let id = 1;
    for (const [key, value] of metricAverage.entries()) {
      tableElems.push(
          new TableRow(id++, key, average(value))
      );
    }
    app.gridData = tableElems;
    app.sampleArr = sampleArr;
    app.guidValue = guidValueInfo;
  };
  reader.readAsText(file);
}

function extractData(contents) {
  /*
   *  Populate guidValue with guidValue objects containing
   *  guid and value from the same type of data.
   */
  const guidValueInfoMap = new Map();
  const result = [];
  const sampleValue = [];
  const dateRangeMap = new Map();
  const other = [];
  /*
   *  Extract every piece of data between <histogram-json> tags;
   *  all data is written between these tags
   */
  const reg = /<histogram-json>(.*?)<\/histogram-json>/g;
  let m = reg.exec(contents);
  while (m !== null) {
    result.push(m[1]);
    m = reg.exec(contents);
  }
  for (const element of result) {
    const e = JSON.parse(element);
    if (e.hasOwnProperty('sampleValues')) {
      sampleValue.push(e);
    } else {
      if (e.type === 'GenericSet') {
        guidValueInfoMap.set(e.guid, e.values);
      } else if (e.type === 'DateRange') {
        guidValueInfoMap.set(e.guid, e.min);
      } else {
        other.push(e);
      }
    }
  }

  return {
    guidValueInfo: guidValueInfoMap,
    guidMinInfo: dateRangeMap,
    otherTypes: other,
    sampleValueArray: sampleValue
  };
}
document.getElementById('file-input')
    .addEventListener('change', readSingleFile, false);
