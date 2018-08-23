'use strict';
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
        app.plotSingleMetric(this.metric.metric,
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
      app.plotSingleMetricWithAllSubdiagnostics(this.metric.metric,
          this.story.story, this.diagnostic);
    }
  }
});
