'use strict';
const getStackedOffsets = (data) => {
  const graph = new GraphData().addData(data);
  graph.plotDot();
  const stackedLocations = graph.dataSources[0].data;
  return stackedLocations.map(({x, y}) => y);
};
describe('DotPlotter', function() {
  describe('dot stacking', function() {
    it('should not stack far away values', function() {
      const data = {
        source: [5, 40, 90, 100],
      };
      const stackedOffsets = getStackedOffsets(data);
      chai.expect(stackedOffsets).to.eql([0, 0, 0, 0]);
    });
    it('should stack duplicates', function() {
      const data = {
        source: [100, 100, 100],
      };
      const stackedOffsets = getStackedOffsets(data);
      chai.expect(stackedOffsets).to.have.members([-1, 0, 1]);
    });
    it('should allow for multiple stacks', function() {
      const data = {
        source: [992, 994, 555, 556, 15],
      };
      const stackedOffsets = getStackedOffsets(data);
      chai.expect(stackedOffsets).to.have.members([-1, 0, -1, 0, 0]);
    });
  });
});
