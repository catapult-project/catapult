'use strict';
describe('MetricSignificance', function() {
  describe('testing for significance', function() {
    const dataOne = [1, 2, 3, 4, 5];
    const dataTwo = [3479, 25983, 2345, 54654, 3245];
    it('should return nothing for no inputs', function() {
      const ms = new MetricSignificance();
      const results = ms.mostSignificant();
      chai.expect(results).to.eql([]);
    });
    it('should return result for significant entry', function() {
      const ms = new MetricSignificance();
      ms.add('metric1', 'label1', dataOne);
      ms.add('metric1', 'label2', dataTwo);
      const results = ms.mostSignificant();
      chai.expect(results.length).to.equal(1);
      chai.expect(results[0].metric).to.equal('metric1');
    });
    it('should return result when data added individually', function() {
      const ms = new MetricSignificance();
      dataOne.forEach(datum => ms.add('metric1', 'label1', [datum]));
      dataTwo.forEach(datum => ms.add('metric1', 'label2', [datum]));
      const results = ms.mostSignificant();
      chai.expect(results.length).to.equal(1);
      chai.expect(results[0].metric).to.equal('metric1');
    });
    it('should throw an error when label has no pair', function() {
      const ms = new MetricSignificance();
      ms.add('metric1', 'label1', dataOne);
      ms.add('metric1', 'label1', dataTwo);
      chai.expect(() => ms.mostSignificant()).to.throw(Error);
    });
    it('should throw an error when metric has more that two labels ',
        function() {
          const ms = new MetricSignificance();
          ms.add('metric1', 'label1', dataOne);
          ms.add('metric1', 'label2', dataOne);
          ms.add('metric1', 'label3', dataOne);
          chai.expect(() => ms.mostSignificant()).to.throw(Error);
        });
    it('should not throw an error when metric has two labels ', function() {
      const ms = new MetricSignificance();
      ms.add('metric1', 'label1', dataOne);
      ms.add('metric1', 'label2', dataOne);
      chai.expect(() => ms.mostSignificant()).to.not.throw(Error);
    });
    it('should only return significant results', function() {
      const noChange = [1, 1, 1, 1, 1];
      const ms = new MetricSignificance();
      ms.add('metric1', 'label1', dataOne);
      ms.add('metric1', 'label2', dataTwo);
      ms.add('metric2', 'label1', noChange);
      ms.add('metric2', 'label2', noChange);
      const results = ms.mostSignificant();
      chai.expect(results.length).to.equal(1);
      chai.expect(results[0].metric).to.equal('metric1');
    });
  });
});
