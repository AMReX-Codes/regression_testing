============
Introduction
============

The regression_testing set of utilities is fully documented in the remainder of
this guide. This page offers a brief introduction to the toolkit and its usage.

Overview
========

regression_testing is a set of regression test management routines for libraries
and applications extending the AMReX framework for block-structured AMR
(adaptive mesh refinement). It allows for full automation of testing procedures,
including compilation and execution of code and analysis routines, as well as
interfacing with version control (namely, Git) and generating HTML output for
display on a webserver. Additional features such as performance monitoring and
assessment of parameter coverage are also available, although the latter is
directly dependent on application output and may not be usable in all cases.

Getting Started
===============

Getting the toolkit
-------------------

The project source may be obtained directly from GitHub_ via git clone with the
following terminal command:

.. code-block:: bash

   $ git clone https://github.com/AMReX-Codes/regression_testing.git

.. _GitHub: https://github.com/AMReX-Codes/regression_testing

Running a test suite
--------------------

The main module is regtest.py, executable from the shell with:

.. code-block:: bash

   $ ./regtest.py [options] configuration_file

To output a verbose description of usage and setup, including optional
arguments, run:

.. code-block:: bash

   $ ./regtest.py -h

Each test suite is defined in a separate `INI formatted`_ configuration file,
containing global settings (e.g. test and web output directories, suite name),
locations and branches for the source library and any dependencies, and
definitions of the test problems with any problem-specific parameters. An
example file (example-tests.ini) using the Castro code may be found in the main
directory of the project repository.

Before any tests may be performed, the suite must be directed to generate
initial benchmarks with the make_benchmarks option:

.. code-block:: bash

   $ ./regtest.py --make_benchmarks "helpful comment" configuration_file

.. _`INI formatted`: https://docs.python.org/3/library/configparser.html#
   supported-ini-file-structure

Quickstart
----------

This section provides a guide describing basic setup.

Using example-tests.ini as a template:

.. rst-class:: open

#. In section [main]:

   a. Set testTopDir to the absolute path to the parent directory of the test
      suite, under which the benchmark and test output directories will be
      nested, and set webTopDir to point to the desired root directory for
      generated webpages.

   #. Configure the build settings if necessary. The sourceTree variable
      determines the build system (C_Src => C++, F_Src => F90, AMReX =>
      standalone AMReX tests), while COMP and FCOMP determine the compilers.
      The numMakeJobs and add_to_c_make_command parameters allow for some
      additional control over the make command.

   #. For email notification when tests fail, set sendEmailWhenFail to 1 and
      edit the emailTo and emailBody settings.The suite also supports automated
      posts to Slack channels with information on test runs (when they begin and
      end, and how many tests failed). To enable this functionality, set
      slack_post to 1, fill in the username and channel fields, and set up a
      webhook in a suite-readable plaintext file (see the Slack documentation).
      Set either parameter to 0 to disable the notifications.

#. Setting up the repositories:

   Each repository needed to build and run the test problems receives its own
   section in the configuration file, containing the repository location and the
   git branch to build from. As the testing routine performs a git pull in each
   repository at the start of a test run, it is recommended to have local clones
   of the repositories that may be used exclusively for testing to avoid
   confusion and potential merge conflicts.

   a. The AMReX repository has a special section in the INI file (aptly
      designated [AMReX]). The dir parameter should be set to the absolute path
      to the repository, and the branch parameter to the branch to pull.

   #. The [source] section corresponds to the repository containing the main
      application code. The parameters should be set as they were for AMReX.

   #. Any additional repositories needed as dependencies or host test
      problems should be listed in subsequent sections of the form
      [extra-<repository_name>].

      These sections each have two additional parameters: comp_string, which
      contains any environment variables needed by the make system (e.g.
      comp_string = MICROPHYSICS_HOME=<value>), and build, which indicates that
      the repository contains build directories for test problems if set to 1.
      The build parameter is optional and defaults to 1.

#. Problem setups:

   Each problem is defined in its own section, labeled with the problem name. A
   number of options are available for test configuration, and are detailed
   later in the guide - this list only touches on the main parameters necessary
   for the tests to function.

   a. If the problem build directory for the problem is not contained in the
      main repository (corresponding to [source]), it is necessary to set the
      extra_build_dir parameter to the section title associated with the correct
      host repository. Otherwise this may be left blank.

   #. Set the value of buildDir to the `relative path` from the repository's root
      directory to the problem build directory. For example, if the repository is
      Castro and the build directory is .../Castro/Exec/Sod_stellar, buildDir
      should be set to Exec/Sod_stellar.

   #. Specify the input file to be supplied to the executable using the inputFile
      parameter, and specify a probin file (with probinFile) if necessary.
