"use strict";

var sinon = require("sinon");
var AssertionError = require("chai").AssertionError;
var expect = require("chai").expect;

describe("Call order", function () {
    var spy1 = sinon.spy(); // Used for testing when setting up tests
    var spy2 = null;
    var spy3 = null;

    beforeEach(function () {
        spy1 = sinon.spy();
        spy2 = sinon.spy();
        spy3 = sinon.spy();
    });

    describe("spy1 calledBefore spy2", function () {
        it("should throw an assertion error when neither spy is called", function () {
            expect(function () {
                spy1.should.have.been.calledBefore(spy2);
            }).to.throw(AssertionError);
        });

        it("should not throw when only spy 1 is called", function () {
            spy1();

            expect(function () {
                spy1.should.have.been.calledBefore(spy2);
            }).to.not.throw();
        });

        it("should throw an assertion error when only spy 2 is called", function () {
            spy2();

            expect(function () {
                spy1.should.have.been.calledBefore(spy2);
            }).to.throw(AssertionError);
        });

        it("should not throw when spy 1 is called before spy 2", function () {
            spy1();
            spy2();

            expect(function () {
                spy1.should.have.been.calledBefore(spy2);
            }).to.not.throw();
        });

        it("should throw an assertion error when spy 1 is called after spy 2", function () {
            spy2();
            spy1();

            expect(function () {
                spy1.should.have.been.calledBefore(spy2);
            }).to.throw(AssertionError);
        });
    });

    if (spy1.calledImmediatelyBefore) {
        describe("spy1 calledImmediatelyBefore spy2", function () {
            it("should throw an assertion error when neither spy is called", function () {
                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when only spy 1 is called", function () {
                spy1();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when only spy 2 is called", function () {
                spy2();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.throw(AssertionError);
            });

            it("should not throw when spy 1 is called immediately before spy 2", function () {
                spy1();
                spy2();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.not.throw();
            });

            it("should throw an assertion error when spy 1 is called before spy 2, but not immediately", function () {
                spy2();
                spy3();
                spy1();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when spy 1 is called after spy 2", function () {
                spy2();
                spy1();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyBefore(spy2);
                }).to.throw(AssertionError);
            });
        });
    }

    describe("spy1 calledAfter spy2", function () {
        it("should throw an assertion error when neither spy is called", function () {
            expect(function () {
                spy1.should.have.been.calledAfter(spy2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when only spy 1 is called", function () {
            spy1();

            expect(function () {
                spy1.should.have.been.calledAfter(spy2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when only spy 2 is called", function () {
            spy2();

            expect(function () {
                spy1.should.have.been.calledAfter(spy2);
            }).to.throw(AssertionError);
        });

        it("should throw an assertion error when spy 1 is called before spy 2", function () {
            spy1();
            spy2();

            expect(function () {
                spy1.should.have.been.calledAfter(spy2);
            }).to.throw(AssertionError);
        });

        it("should not throw when spy 1 is called after spy 2", function () {
            spy2();
            spy1();

            expect(function () {
                spy1.should.have.been.calledAfter(spy2);
            }).to.not.throw();
        });
    });

    if (spy1.calledImmediatelyAfter) {
        describe("spy1 calledImmediatelyAfter spy2", function () {
            it("should throw an assertion error when neither spy is called", function () {
                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when only spy 1 is called", function () {
                spy1();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when only spy 2 is called", function () {
                spy2();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.throw(AssertionError);
            });

            it("should throw an assertion error when spy 1 is called before spy 2", function () {
                spy1();
                spy2();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.throw(AssertionError);
            });

            it("should not throw when spy 1 is called immediately after spy 2", function () {
                spy2();
                spy1();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.not.throw();
            });

            it("should throw an assertion error when spy 1 is called after spy 2, but not immediately", function () {
                spy1();
                spy3();
                spy2();

                expect(function () {
                    spy1.should.have.been.calledImmediatelyAfter(spy2);
                }).to.throw(AssertionError);
            });
        });
    }
});
