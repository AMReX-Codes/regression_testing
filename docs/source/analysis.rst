=================
Analysis Features
=================

Custom Analysis Routines
========================

Monitoring Performance
======================

The toolkit provides features for tracking performance across multiple runs of
a test suite, and warning the developer upon detecting a drop in efficiency.
Plots showing the performance of each test across its entire run history are
automatically generated and linked to at the head of each column on the suite's
main index page. Automated performance monitoring is also available, but is
off by default.

To turn on performance monitoring for an individual test problem, add the line
``check_performance = 1`` to the problem's section in the configuration file.
Following completion of each run of the test problem, its execution time will be
compared with a running average, triggering a warning if the ratio of the two
(execution time / running average) fails to meet a certain threshold. This
threshold may be specified using the ``performance_threshold`` parameter; if
omitted it will default to 1.2, or a 20% drop in performance. The number of
past runs to include in the average may also be specified with the
``runs_to_average`` parameter, which is set to 5 by default.

The same feature may be enabled for the entire suite by supplying the
--check_performance flag on the command line. For a performance threshold of 1.1
and averaging the last 5 runs:

.. code-block:: bash

   $ ./regtest.py --check_performance "1.1" 5 configuration_file

The performance check will then be made for every test problem using those
parameters. Quotes on the parameters are optional.

Parameter Coverage
==================

Parameter coverage reports may also be automatically generated for Castro and
MAESTRO applications, or others that produce job_info files of the same format.
The required format consists of a clearly defined section header containing the
"Parameter" keyword, at least one line of separation (may be anything), and then
a list of parameters starting at the next "=" sign. Covered parameters should be
marked with a [\*], and the parameter section should be the last one in the
file.

If this feature is enabled, the suite will output files titled coverage.out
and coverage_nonspecific.out to the suite run directory under @suiteName@-tests.
The former lists all parameters left uncovered by the test suite, including
those specific to individual test problems, and gives counts of the covered
and uncovered parameters along with the overall coverage percentage. The
latter contains the same information, but omitting test-specific parameters.
These two files are also copied to the corresponding web directory, and
linked to from a table on the test run's index page. The table displays the
coverage percentage and parameter counts from the outfiles.

To enable parameter coverage, add ``reportCoverage = 1`` to the [main] section
of the configuration file. The --with_coverage flag may also be supplied to
the executable, having the same effect:

.. code-block:: bash

   $ ./regtest.py --with_coverage configuration_file

Skipping Comparison
===================

As these routines were designed primarily for regression testing, a comparison
to pre-generated benchmarks is made for each test problem after execution. In
the event that this behavior is not desired (perhaps all analysis is done via
a Python script, as described in `Custom Analysis Routines`_), comparison to
benchmarks may be disabled for an individual test problem by adding the line
``doComparison = 0`` to the problem's section in the configuration file.
Comparison to benchmarks may also be disabled globally by supplying the
--skip_comparison flag to the main module upon execution of the test suite:

.. code-block:: bash

   $ ./regtest.py --skip_comparison configuration_file
