#!/usr/bin/env python

"""
A simple regression test framework for a AMReX-based code

There are several major sections to this source: the runtime parameter
routines, the test suite routines, and the report generation routines.
They are separated as such in this file.

This test framework understands source based out of the F_Src and
C_Src AMReX frameworks.

"""

from __future__ import print_function

import email
import os
import shutil
import smtplib
import string
import sys
import tarfile
import time
import re
import json

import params
import test_util
import test_report as report
import testCoverage as coverage

def find_build_dirs(tests):
    """ given the list of test objects, find the set of UNIQUE build
        directories.  Note if we have the useExtraBuildDir flag set """

    build_dirs = []
    reclean = []

    for obj in tests:

        # keep track of the build directory and which source tree it is
        # in (e.g. the extra build dir)

        # first find the list of unique build directories
        dir_pair = (obj.buildDir, obj.extra_build_dir)
        if build_dirs.count(dir_pair) == 0:
            build_dirs.append(dir_pair)


        # re-make all problems that specify an extra compile argument,
        # just to make sure that any unique build commands are seen.
        if not obj.addToCompileString == "":
            reclean.append(dir_pair)

    for bdir, _ in reclean:
        for obj in tests:
            if obj.buildDir == bdir:
                obj.reClean = 1

    return build_dirs




def cmake_setup(suite):
    "Setup for cmake"

    #--------------------------------------------------------------------------
    # build AMReX with CMake
    #--------------------------------------------------------------------------
    # Configure Amrex
    builddir, installdir = suite.cmake_config( name       = "AMReX",
                                               path       = suite.amrex_dir,
                                               configOpts = suite.amrex_cmake_opts,
                                               install    = 1)

    suite.amrex_install_dir = installdir

    # Define additional env variable to point to AMReX install location
    env = {'AMREX_HOME':installdir}


    # Install
    rc, comp_string = suite.cmake_build( name   = "AMReX",
                                         target = 'install',
                                         path   = builddir,
                                         env    = env)

    # If AMReX build fails, issue a catastrophic error
    if not rc == 0:
        errstr  = "\n \nERROR! AMReX build failed \n"
        errstr += "Check {}AMReX.cmake.log for more information.".format(suite.full_test_dir)
        sys.exit(errstr)


    #--------------------------------------------------------------------------
    # Configure main suite with CMake: build will be performed only when
    # needed for tests
    #--------------------------------------------------------------------------
    builddir, installdir = suite.cmake_config( name       = suite.suiteName,
                                               path       = suite.source_dir,
                                               configOpts = suite.source_cmake_opts,
                                               install    = 0,
                                               env        = env)

    suite.source_build_dir = builddir

    return rc




def copy_benchmarks(old_full_test_dir, full_web_dir, test_list, bench_dir, log):
    """ copy the last plotfile output from each test in test_list
        into the benchmark directory.  Also copy the diffDir, if
        it exists """
    td = os.getcwd()

    for t in test_list:
        wd = "{}/{}".format(old_full_test_dir, t.name)
        os.chdir(wd)

        if t.compareFile == "" and t.outputFile == "":
            p = t.get_compare_file(output_dir=wd)
        elif not t.outputFile == "":
            if not os.path.exists(t.outputFile):
                p = test_util.get_recent_filename(wd, t.outputFile, ".tgz")
            else:
                p = t.outputFile
        else:
            if not os.path.exists(t.compareFile):
                p = test_util.get_recent_filename(wd, t.compareFile, ".tgz")
            else:
                p = t.compareFile

        if p != "" and p is not None:
            if p.endswith(".tgz"):
                try:
                    tg = tarfile.open(name=p, mode="r:gz")
                    tg.extractall()
                except:
                    log.fail("ERROR extracting tarfile")
                else:
                    tg.close()
                idx = p.rfind(".tgz")
                p = p[:idx]

            store_file = p
            if not t.outputFile == "":
                store_file = "{}_{}".format(t.name, p)

            try: shutil.rmtree("{}/{}".format(bench_dir, store_file))
            except: pass
            shutil.copytree(p, "{}/{}".format(bench_dir, store_file))

            with open("{}/{}.status".format(full_web_dir, t.name), 'w') as cf:
                cf.write("benchmarks updated.  New file:  {}\n".format(store_file))

        else:   # no benchmark exists
            with open("{}/{}.status".format(full_web_dir, t.name), 'w') as cf:
                cf.write("benchmarks update failed")

        # is there a diffDir to copy too?
        if not t.diffDir == "":
            diff_dir_bench = "{}/{}_{}".format(bench_dir, t.name, t.diffDir)
            if os.path.isdir(diff_dir_bench):
                shutil.rmtree(diff_dir_bench)
                shutil.copytree(t.diffDir, diff_dir_bench)
            else:
                if os.path.isdir(t.diffDir):
                    try:
                        shutil.copytree(t.diffDir, diff_dir_bench)
                    except IOError:
                        log.warn("file {} not found".format(t.diffDir))
                    else:
                        log.log("new diffDir: {}_{}".format(t.name, t.diffDir))
                else:
                    try:
                        shutil.copy(t.diffDir, diff_dir_bench)
                    except IOError:
                        log.warn("file {} not found".format(t.diffDir))
                    else:
                        log.log("new diffDir: {}_{}".format(t.name, t.diffDir))

        os.chdir(td)

def get_variable_names(suite, plotfile):
    """ uses fvarnames to extract the names of variables
        stored in a plotfile """

    # Run fvarnames
    command = "{} {}".format(suite.tools["fvarnames"], plotfile)
    sout, serr, ierr = test_util.run(command)

    if ierr != 0:
        return serr

    # Split on whitespace
    vars = re.split("\s+", sout)[2:-1:2]

    return set(vars)

def process_comparison_results(stdout, vars, test):
    """ checks the output of fcompare (passed in as stdout)
        to determine whether all relative errors fall within
        the test's tolerance """

    # Alternative solution - just split on whitespace
    # and iterate through resulting list, attempting
    # to convert the next two items to floats. Assume
    # the current item is a variable if successful.

    # Split on whitespace
    regex = "\s+"
    words = re.split(regex, stdout)

    indices = filter(lambda i: words[i] in vars, range(len(words)))

    for i in indices:
        var, abs_err, rel_err = words[i: i + 3]
        if abs(test.tolerance) <= abs(float(rel_err)): return False

    return True

def test_performance(test, suite, runtimes):
    """ outputs a warning if the execution time of the test this run
        does not compare favorably to past logged times """

    if test.name not in runtimes: return
    runtimes = runtimes[test.name]["runtimes"]

    if len(runtimes) < 1:
        suite.log.log("no completed runs found")
        return

    num_times = len(runtimes)
    suite.log.log("{} completed run(s) found".format(num_times))
    suite.log.log("checking performance ...")

    # Slice out correct number of times
    run_diff = num_times - test.runs_to_average
    if run_diff > 0:
        runtimes = runtimes[:-run_diff]
        num_times = test.runs_to_average
    else:
        test.runs_to_average = num_times

    test.past_average = sum(runtimes) / num_times

    # Test against threshold
    meets_threshold, percentage, compare_str = test.measure_performance()
    if meets_threshold is not None and not meets_threshold:
        warn_msg = "test ran {:.1f}% {} than running average of the past {} runs"
        warn_msg = warn_msg.format(percentage, compare_str, num_times)
        suite.log.warn(warn_msg)

def determine_coverage(suite):

    try:
        results = coverage.main(suite.full_test_dir)
    except:
        suite.log.warn("error generating parameter coverage reports, check formatting")
        return

    if not any([res is None for res in results]):

        suite.covered_frac = results[0]
        suite.total = results[1]
        suite.covered_nonspecific_frac = results[2]
        suite.total_nonspecific = results[3]

        spec_file = os.path.join(suite.full_test_dir, coverage.SPEC_FILE)
        nonspec_file = os.path.join(suite.full_test_dir, coverage.NONSPEC_FILE)

        shutil.copy(spec_file, suite.full_web_dir)
        shutil.copy(nonspec_file, suite.full_web_dir)

def test_suite(argv):
    """
    the main test suite driver
    """

    # parse the commandline arguments
    args = test_util.get_args(arg_string=argv)

    # read in the test information
    suite, test_list = params.load_params(args)

    active_test_list = [t.name for t in test_list]

    test_list = suite.get_tests_to_run(test_list)

    suite.log.skip()
    suite.log.bold("running tests: ")
    suite.log.indent()
    for obj in test_list:
        suite.log.log(obj.name)
    suite.log.outdent()

    if not args.complete_report_from_crash == "":

        # make sure the web directory from the crash run exists
        suite.full_web_dir = "{}/{}/".format(
            suite.webTopDir, args.complete_report_from_crash)
        if not os.path.isdir(suite.full_web_dir):
            suite.log.fail("Crash directory does not exist")

        suite.test_dir = args.complete_report_from_crash

        # find all the tests that completed in that web directory
        tests = []
        test_file = ""
        was_benchmark_run = 0
        for sfile in os.listdir(suite.full_web_dir):
            if os.path.isfile(sfile) and sfile.endswith(".status"):
                index = string.rfind(sfile, ".status")
                tests.append(sfile[:index])

                with open(suite.full_web_dir + sfile, "r") as f:
                    for line in f:
                        if line.find("benchmarks updated") > 0:
                            was_benchmark_run = 1

            if os.path.isfile(sfile) and sfile.endswith(".ini"):
                test_file = sfile


        # create the report for this test run
        num_failed = report.report_this_test_run(suite, was_benchmark_run,
                                                 "recreated report after crash of suite",
                                                 "", tests, test_file)

        # create the suite report
        suite.log.bold("creating suite report...")
        report.report_all_runs(suite, active_test_list)
        suite.log.close_log()
        sys.exit("done")


    #--------------------------------------------------------------------------
    # check bench dir and create output directories
    #--------------------------------------------------------------------------
    all_compile = all([t.compileTest == 1 for t in test_list])

    if not all_compile:
        bench_dir = suite.get_bench_dir()

    if not args.copy_benchmarks is None:
        last_run = suite.get_last_run()

    suite.make_test_dirs()

    if suite.slack_post:
        msg = "> {} ({}) test suite started, id: {}\n> {}".format(
            suite.suiteName, suite.sub_title, suite.test_dir, args.note)
        suite.slack_post_it(msg)

    if not args.copy_benchmarks is None:
        old_full_test_dir = suite.testTopDir + suite.suiteName + "-tests/" + last_run
        copy_benchmarks(old_full_test_dir, suite.full_web_dir,
                        test_list, bench_dir, suite.log)

        # here, args.copy_benchmarks plays the role of make_benchmarks
        num_failed = report.report_this_test_run(suite, args.copy_benchmarks,
                                                 "copy_benchmarks used -- no new tests run",
                                                 "",
                                                 test_list, args.input_file[0])
        report.report_all_runs(suite, active_test_list)

        if suite.slack_post:
            msg = "> copied benchmarks\n> {}".format(args.copy_benchmarks)
            suite.slack_post_it(msg)

        sys.exit("done")


    #--------------------------------------------------------------------------
    # figure out what needs updating and do the git updates, save the
    # current hash / HEAD, and make a ChangeLog
    # --------------------------------------------------------------------------
    now = time.localtime(time.time())
    update_time = time.strftime("%Y-%m-%d %H:%M:%S %Z", now)

    no_update = args.no_update.lower()
    if not args.copy_benchmarks is None:
        no_update = "all"

    # the default is to update everything, unless we specified a hash
    # when constructing the Repo object
    if no_update == "none":
        pass

    elif no_update == "all":
        for k in suite.repos:
            suite.repos[k].update = False

    else:
        nouplist = [k.strip() for k in no_update.split(",")]

        for repo in suite.repos.keys():
            if repo.lower() in nouplist:
                suite.repos[repo].update = False

    os.chdir(suite.testTopDir)

    for k in suite.repos:
        suite.log.skip()
        suite.log.bold("repo: {}".format(suite.repos[k].name))
        suite.log.indent()

        if suite.repos[k].update or suite.repos[k].hash_wanted:
            suite.repos[k].git_update()

        suite.repos[k].save_head()

        if suite.repos[k].update:
            suite.repos[k].make_changelog()

        suite.log.outdent()


    # keep track if we are running on any branch that is not the suite
    # default
    branches = [suite.repos[r].branch_wanted for r in suite.repos]
    if not all(suite.default_branch == b for b in branches):
        suite.log.warn("some git repos are not on the default branch")
        bf = open("{}/branch.status".format(suite.full_web_dir), "w")
        bf.write("branch different than suite default")
        bf.close()

    #--------------------------------------------------------------------------
    # build the tools and do a make clean, only once per build directory
    #--------------------------------------------------------------------------
    suite.build_tools(test_list)

    all_build_dirs = find_build_dirs(test_list)

    suite.log.skip()
    suite.log.bold("make clean in...")

    for d, source_tree in all_build_dirs:

        if not source_tree == "":
            suite.log.log("{} in {}".format(d, source_tree))
            os.chdir(suite.repos[source_tree].dir + d)
            suite.make_realclean(repo=source_tree)
        else:
            suite.log.log("{}".format(d))
            os.chdir(suite.source_dir + d)
            if suite.sourceTree in ["AMReX", "amrex"]:
                suite.make_realclean(repo="AMReX")
            else:
                suite.make_realclean()

    os.chdir(suite.testTopDir)


    #--------------------------------------------------------------------------
    # Setup Cmake if needed
    #--------------------------------------------------------------------------
    if ( suite.useCmake ):
        cmake_setup(suite)


    #--------------------------------------------------------------------------
    # Get execution times from previous runs
    #--------------------------------------------------------------------------
    runtimes = suite.get_wallclock_history()

    #--------------------------------------------------------------------------
    # main loop over tests
    #--------------------------------------------------------------------------
    for test in test_list:

        suite.log.outdent()  # just to make sure we have no indentation
        suite.log.skip()
        suite.log.bold("working on test: {}".format(test.name))
        suite.log.indent()

        if not args.make_benchmarks is None and (test.restartTest or test.compileTest or
                                                 test.selfTest):
            suite.log.warn("benchmarks not needed for test {}".format(test.name))
            continue

        output_dir = suite.full_test_dir + test.name + '/'
        os.mkdir(output_dir)
        test.output_dir = output_dir


        #----------------------------------------------------------------------
        # compile the code
        #----------------------------------------------------------------------
        if not test.extra_build_dir == "":
            bdir = suite.repos[test.extra_build_dir].dir + test.buildDir
        else:
            bdir = suite.source_dir + test.buildDir

        # # For cmake builds, there is only one build dir
        # if ( suite.useCmake ): bdir = suite.source_build_dir

        os.chdir(bdir)
        # Create directory for executables
        binDir = 'Bin'
        if not os.path.exists(binDir):
            os.mkdir(binDir)

        if test.reClean == 1:
            # for one reason or another, multiple tests use different
            # build options, make clean again to be safe
            suite.log.log("re-making clean...")
            if not test.extra_build_dir == "":
                suite.make_realclean(repo=test.extra_build_dir)
            elif suite.sourceTree in ["AMReX", "amrex"]:
                suite.make_realclean(repo="AMReX")
            else:
                suite.make_realclean()

        # Register start time
        test.build_time = time.time()

        suite.log.log("building...")

        coutfile="{}/{}.make.out".format(output_dir, test.name)

        # First check if a previous test was compiled with the same options
        if suite.sourceTree == "C_Src" or test.testSrcTree == "C_Src":
            comp_string = suite.get_comp_string_c(test=test, outfile=coutfile)
        elif suite.sourceTree == "F_Src" or test.testSrcTree == "F_Src":
            comp_string = suite.get_comp_string_f(test=test, outfile=coutfile)
        found_previous_test = False
        # Loop over the existing tests
        for previous_test in test_list:
            # Check if the compile command was the same
            if previous_test.comp_string == comp_string:
                found_previous_test = True
                break
        if found_previous_test:
            # Avoid recompiling in this case
            suite.log.log("found pre-built executable for this test")
            rc = 0
            executable = previous_test.executable
        else:
            # Recompile
            if suite.sourceTree == "C_Src" or test.testSrcTree == "C_Src":
                if ( suite.useCmake ) :
                    comp_string, rc = suite.build_test_cmake(test=test, outfile=coutfile)
                else:
                    comp_string, rc = suite.build_c(test=test, outfile=coutfile)
                executable = test_util.get_recent_filename(bdir, "", ".ex")

            elif suite.sourceTree == "F_Src" or test.testSrcTree == "F_Src":
                comp_string, rc = suite.build_f(test=test, outfile=coutfile)
                executable = test_util.get_recent_filename(bdir, "main", ".exe")
            # Copy executable to bin directory
            if executable is not None:
                shutil.copy( executable, binDir )
            
        test.comp_string = comp_string
        test.executable = executable

        # make return code is 0 if build was successful
        if rc == 0: test.compile_successful = True
        # Compute compile time
        test.build_time = time.time() - test.build_time

        # copy the make.out into the web directory
        outfile = "{}/{}.make.out".format(output_dir, test.name)
        if os.path.exists(outfile):
            shutil.copy(outfile, suite.full_web_dir)

        if not test.compile_successful:
            error_msg = "ERROR: compilation failed"
            report.report_single_test(suite, test, test_list, failure_msg=error_msg)
            # Print compilation error message (useful for Travis tests)
            with open(outfile) as f:
                print( f.read() )

            continue

        if test.compileTest:
            suite.log.log("creating problem test report ...")
            report.report_single_test(suite, test, test_list)
            continue


        #----------------------------------------------------------------------
        # copy the necessary files over to the run directory
        #----------------------------------------------------------------------
        suite.log.log("copying files to run directory...")

        needed_files = []
        if executable is not None:
            needed_files.append((os.path.join(binDir,executable), "copy"))

        if test.run_as_script:
            needed_files.append((test.run_as_script, "copy"))

        if test.inputFile:

            needed_files.append((test.inputFile, "copy"))
            # strip out any sub-directory from the build dir
            test.inputFile = os.path.basename(test.inputFile)

        if test.probinFile != "":
            needed_files.append((test.probinFile, "copy"))
            # strip out any sub-directory from the build dir
            test.probinFile = os.path.basename(test.probinFile)

        for auxf in test.auxFiles:
            needed_files.append((auxf, "copy"))

        # if any copy/move fail, we move onto the next test
        skip_to_next_test = 0
        for nfile, action in needed_files:
            if action == "copy":
                act = shutil.copy
            elif action == "move":
                act = shutil.move
            else:
                suite.log.fail("invalid action")

            try: act(nfile, output_dir)
            except IOError:
                error_msg = "ERROR: unable to {} file {}".format(action, nfile)
                report.report_single_test(suite, test, test_list, failure_msg=error_msg)
                skip_to_next_test = 1
                break

        if skip_to_next_test: continue

        skip_to_next_test = 0
        for lfile in test.linkFiles:
            if not os.path.exists(lfile):
                error_msg = "ERROR: link file {} does not exist".format(lfile)
                report.report_single_test(suite, test, test_list, failure_msg=error_msg)
                skip_to_next_test = 1
                break

            else:
                link_source = os.path.abspath(lfile)
                link_name = os.path.join(output_dir, os.path.basename(lfile))
                try: os.symlink(link_source, link_name)
                except IOError:
                    error_msg = "ERROR: unable to symlink link file: {}".format(lfile)
                    report.report_single_test(suite, test, test_list, failure_msg=error_msg)
                    skip_to_next_test = 1
                    break

        if skip_to_next_test: continue


        #----------------------------------------------------------------------
        # run the test
        #----------------------------------------------------------------------
        suite.log.log("running the test...")

        os.chdir(output_dir)

        test.wall_time = time.time()

        if suite.sourceTree == "C_Src" or test.testSrcTree == "C_Src":

            base_cmd = "./{} {} {}={}_plt amr.check_file={}_chk".format(
                executable, test.inputFile, suite.plot_file_name, test.name, test.name)

            # keep around the checkpoint files only for the restart runs
            if test.restartTest:
                base_cmd += " amr.checkpoint_files_output=1 amr.check_int=%d" % \
                                (test.restartFileNum)

            base_cmd += " {} {}".format(suite.globalAddToExecString, test.runtime_params)

        elif suite.sourceTree == "F_Src" or test.testSrcTree == "F_Src":

            base_cmd = "./{} {} --plot_base_name {}_plt --check_base_name {}_chk ".format(
                executable, test.inputFile, test.name, test.name)

            # keep around the checkpoint files only for the restart runs
            if not test.restartTest: base_cmd += " --chk_int 0 "

            base_cmd += "{} {}".format(suite.globalAddToExecString, test.runtime_params)

        if args.with_valgrind:
            base_cmd = "valgrind " + args.valgrind_options + " " + base_cmd

        if test.run_as_script:
            base_cmd = "./{} {}".format(test.run_as_script, test.script_args)

        if test.customRunCmd is not None:
            base_cmd = test.customRunCmd



        suite.run_test(test, base_cmd)

        # if it is a restart test, then rename the final output file and
        # restart the test
        if test.restartTest:
            skip_restart = False

            last_file = test.get_compare_file(output_dir=output_dir)

            if last_file == "":
                error_msg = "ERROR: test did not produce output.  Restart test not possible"
                skip_restart = True

            if len(test.find_backtrace()) > 0:
                error_msg = "ERROR: test produced backtraces.  Restart test not possible"
                skip_restart = True

            if skip_restart:
                # copy what we can
                test.wall_time = time.time() - test.wall_time
                shutil.copy(test.outfile, suite.full_web_dir)
                if os.path.isfile(test.errfile):
                    shutil.copy(test.errfile, suite.full_web_dir)
                    test.has_stderr = True
                suite.copy_backtrace(test)
                report.report_single_test(suite, test, test_list, failure_msg=error_msg)
                continue
            orig_last_file = "orig_{}".format(last_file)
            shutil.move(last_file, orig_last_file)

            if test.diffDir:
                orig_diff_dir = "orig_{}".format(test.diffDir)
                shutil.move(test.diffDir, orig_diff_dir)

            # get the file number to restart from
            restart_file = "%s_chk%5.5d" % (test.name, test.restartFileNum)

            suite.log.log("restarting from {} ... ".format(restart_file))

            if suite.sourceTree == "C_Src" or test.testSrcTree == "C_Src":

                base_cmd = "./{} {} {}={}_plt amr.check_file={}_chk amr.checkpoint_files_output=0 amr.restart={}".format(
                    executable, test.inputFile, suite.plot_file_name, test.name, test.name, restart_file)

            elif suite.sourceTree == "F_Src" or test.testSrcTree == "F_Src":

                base_cmd = "./{} {} --plot_base_name {}_plt --check_base_name {}_chk --chk_int 0 --restart {} {}".format(
                    executable, test.inputFile, test.name, test.name, test.restartFileNum, suite.globalAddToExecString)

            suite.run_test(test, base_cmd)

        test.wall_time = time.time() - test.wall_time

        # Check for performance drop
        if test.check_performance: test_performance(test, suite, runtimes)

        #----------------------------------------------------------------------
        # do the comparison
        #----------------------------------------------------------------------
        output_file = ""
        if not test.selfTest:

            if test.outputFile == "":
                if test.compareFile == "":
                    compare_file = test.get_compare_file(output_dir=output_dir)
                else:
                    # we specified the name of the file we want to
                    # compare to -- make sure it exists
                    compare_file = test.compareFile
                    if not os.path.exists(compare_file):
                        compare_file = ""

                output_file = compare_file
            else:
                output_file = test.outputFile
                compare_file = test.name+'_'+output_file


            # get the number of levels for reporting
            if False:

                prog = "{} -l {}".format(suite.tools["fboxinfo"], output_file)
                stdout0, stderr0, rc = test_util.run(prog)
                test.nlevels = stdout0.rstrip('\n')
                if not type(params.convert_type(test.nlevels)) is int:
                    test.nlevels = ""

            if args.make_benchmarks is None and test.doComparison:

                suite.log.log("doing the comparison...")
                suite.log.indent()
                suite.log.log("comparison file: {}".format(output_file))

                test.compare_file_used = output_file

                if not test.restartTest:
                    bench_file = bench_dir + compare_file
                else:
                    bench_file = orig_last_file

                # see if it exists
                # note, with AMReX, the plotfiles are actually directories
                # switched to exists to handle the run_as_script case

                if not os.path.exists(bench_file):
                    suite.log.warn("no corresponding benchmark found")
                    bench_file = ""

                    with open(test.comparison_outfile, 'w') as cf:
                        cf.write("WARNING: no corresponding benchmark found\n")
                        cf.write("         unable to do a comparison\n")

                else:
                    if not compare_file == "":

                        suite.log.log("benchmark file: {}".format(bench_file))

                        if test.run_as_script:

                            command = "diff {} {}".format(bench_file, output_file)

                        else:

                            command = "{} -n 0 {} {}".format(suite.tools["fcompare"],
                                    bench_file, output_file)

                        sout, serr, ierr = test_util.run(command,
                                                         outfile=test.comparison_outfile,
                                                         store_command=True)

                        if test.run_as_script:

                            test.compare_successful = not sout

                        # Comparison within tolerance - reliant on fvarnames and fcompare
                        elif test.tolerance is not None:

                            vars = get_variable_names(suite, bench_file)
                            test.compare_successful = process_comparison_results(sout, vars, test)

                        else:

                            test.compare_successful = ierr == 0

                        if test.compareParticles:
                            for ptype in test.particleTypes.strip().split():
                                command = "{} {} {} {}".format(
                                    suite.tools["particle_compare"], bench_file, output_file, ptype)

                                sout, serr, ierr = test_util.run(command,
                                                                 outfile=test.comparison_outfile, store_command=True)

                                test.compare_successful = test.compare_successful and not ierr

                    else:
                        suite.log.warn("unable to do a comparison")

                        with open(test.comparison_outfile, 'w') as cf:
                            cf.write("WARNING: run did not produce any output\n")
                            cf.write("         unable to do a comparison\n")

                suite.log.outdent()

                if not test.diffDir == "":
                    if not test.restartTest:
                        diff_dir_bench = bench_dir + '/' + test.name + '_' + test.diffDir
                    else:
                        diff_dir_bench = orig_diff_dir

                    suite.log.log("doing the diff...")
                    suite.log.log("diff dir: {}".format(test.diffDir))

                    command = "diff {} -r {} {}".format(
                        test.diffOpts, diff_dir_bench, test.diffDir)

                    outfile = test.comparison_outfile
                    sout, serr, diff_status = test_util.run(command, outfile=outfile, store_command=True)

                    if diff_status == 0:
                        diff_successful = True
                        with open(test.comparison_outfile, 'a') as cf:
                            cf.write("\ndiff was SUCCESSFUL\n")
                    else:
                        diff_successful = False

                    test.compare_successful = test.compare_successful and diff_successful

            elif test.doComparison:   # make_benchmarks

                if not compare_file == "":

                    if not output_file == compare_file:
                        source_file = output_file
                    else:
                        source_file = compare_file

                    suite.log.log("storing output of {} as the new benchmark...".format(test.name))
                    suite.log.indent()
                    suite.log.warn("new benchmark file: {}".format(compare_file))
                    suite.log.outdent()

                    if test.run_as_script:

                        bench_path = os.path.join(bench_dir, compare_file)
                        try: os.remove(bench_path)
                        except: pass
                        shutil.copy(source_file, bench_path)

                    else:

                        try: shutil.rmtree("{}/{}".format(bench_dir, compare_file))
                        except: pass
                        shutil.copytree(source_file, "{}/{}".format(bench_dir, compare_file))

                    with open("{}.status".format(test.name), 'w') as cf:
                        cf.write("benchmarks updated.  New file:  {}\n".format(compare_file) )

                else:
                    with open("{}.status".format(test.name), 'w') as cf:
                        cf.write("benchmarks failed")

                    # copy what we can
                    shutil.copy(test.outfile, suite.full_web_dir)
                    if os.path.isfile(test.errfile):
                        shutil.copy(test.errfile, suite.full_web_dir)
                        test.has_stderr = True
                    suite.copy_backtrace(test)
                    error_msg = "ERROR: runtime failure during benchmark creation"
                    report.report_single_test(suite, test, test_list, failure_msg=error_msg)


                if not test.diffDir == "":
                    diff_dir_bench = "{}/{}_{}".format(bench_dir, test.name, test.diffDir)
                    if os.path.isdir(diff_dir_bench):
                        shutil.rmtree(diff_dir_bench)
                        shutil.copytree(test.diffDir, diff_dir_bench)
                    else:
                        if os.path.isdir(test.diffDir):
                            shutil.copytree(test.diffDir, diff_dir_bench)
                        else:
                            shutil.copy(test.diffDir, diff_dir_bench)
                    suite.log.log("new diffDir: {}_{}".format(test.name, test.diffDir))

            else:  # don't do a pltfile comparison
                test.compare_successful = True

        else:   # selfTest

            if args.make_benchmarks is None:

                suite.log.log("looking for selfTest success string: {} ...".format(test.stSuccessString))

                try: of = open(test.outfile, 'r')
                except IOError:
                    suite.log.warn("no output file found")
                    out_lines = ['']
                else:
                    out_lines = of.readlines()

                    # successful comparison is indicated by presence
                    # of success string
                    for line in out_lines:
                        if line.find(test.stSuccessString) >= 0:
                            test.compare_successful = True
                            break

                    of.close()

                with open(test.comparison_outfile, 'w') as cf:
                    if test.compare_successful:
                        cf.write("SELF TEST SUCCESSFUL\n")
                    else:
                        cf.write("SELF TEST FAILED\n")


        #----------------------------------------------------------------------
        # do any requested visualization (2- and 3-d only) and analysis
        #----------------------------------------------------------------------
        if not test.selfTest:
            if output_file != "":
                if args.make_benchmarks is None:

                    # get any parameters for the summary table
                    job_info_file = "{}/job_info".format(output_file)
                    if os.path.isfile(job_info_file):
                        test.has_jobinfo = 1

                    try: jif = open(job_info_file, "r")
                    except:
                        suite.log.warn("unable to open the job_info file")
                    else:
                        job_file_lines = jif.readlines()
                        jif.close()

                        if suite.summary_job_info_field1 is not "":
                            for l in job_file_lines:
                                if l.startswith(suite.summary_job_info_field1.strip()) and l.find(":") >= 0:
                                    _tmp = l.split(":")[1]
                                    idx = _tmp.rfind("/") + 1
                                    test.job_info_field1 = _tmp[idx:]
                                    break

                        if suite.summary_job_info_field2 is not "":
                            for l in job_file_lines:
                                if l.startswith(suite.summary_job_info_field2.strip()) and l.find(":") >= 0:
                                    _tmp = l.split(":")[1]
                                    idx = _tmp.rfind("/") + 1
                                    test.job_info_field2 = _tmp[idx:]
                                    break

                        if suite.summary_job_info_field3 is not "":
                            for l in job_file_lines:
                                if l.startswith(suite.summary_job_info_field3.strip()) and l.find(":") >= 0:
                                    _tmp = l.split(":")[1]
                                    idx = _tmp.rfind("/") + 1
                                    test.job_info_field3 = _tmp[idx:]
                                    break

                    # visualization
                    if test.doVis:

                        if test.dim == 1:
                            suite.log.log("Visualization not supported for dim = {}".format(test.dim))
                        else:
                            suite.log.log("doing the visualization...")
                            tool = suite.tools["fsnapshot"]
                            test_util.run('{} --palette {}/Palette --variable "{}" "{}"'.format(
                                tool, suite.f_compare_tool_dir, test.visVar, output_file))

                            # convert the .ppm files into .png files
                            ppm_file = test_util.get_recent_filename(output_dir, "", ".ppm")
                            if not ppm_file is None:
                                png_file = ppm_file.replace(".ppm", ".png")
                                test_util.run("convert {} {}".format(ppm_file, png_file))
                                test.png_file = png_file

                    # analysis
                    if not test.analysisRoutine == "":

                        suite.log.log("doing the analysis...")
                        if not test.extra_build_dir == "":
                            tool = "{}/{}".format(suite.repos[test.extra_build_dir].dir, test.analysisRoutine)
                        else:
                            tool = "{}/{}".format(suite.source_dir, test.analysisRoutine)

                        shutil.copy(tool, os.getcwd())

                        if test.analysisMainArgs == "":
                            option = ""
                        else:
                            option = eval("suite.{}".format(test.analysisMainArgs))

                        cmd_name = os.path.basename(test.analysisRoutine)
                        cmd_string = "./{} {} {}".format(cmd_name, option, output_file)
                        outfile = "{}.analysis.out".format(test.name)
                        _, _, rc = test_util.run(cmd_string, outfile=outfile, store_command=True)

                        if rc == 0:
                            analysis_successful = True
                        else:
                            analysis_successful = False
                            suite.log.warn("analysis failed...")
                            # Print analysis error message (useful for Travis tests)
                            with open(outfile) as f:
                                print( f.read() )
                            
                        test.analysis_successful = analysis_successful

            else:
                if test.doVis or test.analysisRoutine != "":
                    suite.log.warn("no output file.  Skipping visualization")

        #----------------------------------------------------------------------
        # if the test ran and passed, add its runtime to the dictionary
        #----------------------------------------------------------------------

        if test.record_runtime(suite):
            test_dict = runtimes.setdefault(test.name, suite.timing_default)
            test_dict["runtimes"].insert(0, test.wall_time)
            test_dict["dates"].insert(0, suite.test_dir.rstrip("/"))

        #----------------------------------------------------------------------
        # move the output files into the web directory
        #----------------------------------------------------------------------
        if args.make_benchmarks is None:
            shutil.copy(test.outfile, suite.full_web_dir)
            if os.path.isfile(test.errfile):
                shutil.copy(test.errfile, suite.full_web_dir)
                test.has_stderr = True
            if test.doComparison:
                shutil.copy(test.comparison_outfile, suite.full_web_dir)
            try:
                shutil.copy("{}.analysis.out".format(test.name), suite.full_web_dir)
            except:
                pass

            if test.inputFile:

                shutil.copy(test.inputFile, "{}/{}.{}".format(
                    suite.full_web_dir, test.name, test.inputFile) )

            if test.has_jobinfo:
                shutil.copy(job_info_file, "{}/{}.job_info".format(
                    suite.full_web_dir, test.name))

            if suite.sourceTree == "C_Src" and test.probinFile != "":
                shutil.copy(test.probinFile, "{}/{}.{}".format(
                    suite.full_web_dir, test.name, test.probinFile) )

            for af in test.auxFiles:

                # strip out any sub-directory under build dir for the aux file
                # when copying
                shutil.copy(os.path.basename(af),
                            "{}/{}.{}".format(suite.full_web_dir,
                                              test.name, os.path.basename(af)) )

            if not test.png_file is None:
                try: shutil.copy(test.png_file, suite.full_web_dir)
                except IOError:
                    # visualization was not successful.  Reset image
                    test.png_file = None

            if not test.analysisRoutine == "":
                try: shutil.copy(test.analysisOutputImage, suite.full_web_dir)
                except IOError:
                    # analysis was not successful.  Reset the output image
                    test.analysisOutputImage = ""

            # were any Backtrace files output (indicating a crash)
            suite.copy_backtrace(test)

        else:
            if test.doComparison:
                shutil.copy("{}.status".format(test.name), suite.full_web_dir)


        #----------------------------------------------------------------------
        # Print execution time
        #----------------------------------------------------------------------
        suite.log.log("execution time: %.1fs" %test.wall_time)

        #----------------------------------------------------------------------
        # write the report for this test
        #----------------------------------------------------------------------
        if args.make_benchmarks is None:
            suite.log.log("creating problem test report ...")
            report.report_single_test(suite, test, test_list)

    #--------------------------------------------------------------------------
    # Clean Cmake build and install directories if needed
    #--------------------------------------------------------------------------
    if ( suite.useCmake ):
        suite.cmake_clean("AMReX", suite.amrex_dir)
        suite.cmake_clean(suite.suiteName, suite.source_dir)

    #--------------------------------------------------------------------------
    # jsonify and save runtimes
    #--------------------------------------------------------------------------
    file_path = suite.get_wallclock_file()
    with open(file_path, 'w') as json_file: json.dump(runtimes, json_file)

    #--------------------------------------------------------------------------
    # parameter coverage
    #--------------------------------------------------------------------------
    if suite.reportCoverage: determine_coverage(suite)

    #--------------------------------------------------------------------------
    # write the report for this instance of the test suite
    #--------------------------------------------------------------------------
    suite.log.outdent()
    suite.log.skip()
    suite.log.bold("creating new test report...")
    num_failed = report.report_this_test_run(suite, args.make_benchmarks, args.note,
                                             update_time,
                                             test_list, args.input_file[0])


    # make sure that all of the files in the web directory are world readable
    for file in os.listdir(suite.full_web_dir):
       current_file = suite.full_web_dir + file

       if os.path.isfile(current_file):
          os.chmod(current_file, 0o644)

    # reset the branch to what it was originally
    suite.log.skip()
    suite.log.bold("reverting git branches/hashes")
    suite.log.indent()

    for k in suite.repos:
        if suite.repos[k].update or suite.repos[k].hash_wanted:
            suite.repos[k].git_back()

    suite.log.outdent()

    # For temporary run, return now without creating suite report.
    if args.do_temp_run:
        suite.delete_tempdirs()
        return num_failed


    # store an output file in the web directory that can be parsed easily by
    # external program
    name = "source"
    if suite.sourceTree in ["AMReX", "amrex"]: name = "AMReX"
    branch = ''
    if suite.repos[name].branch_wanted:
        branch = suite.repos[name].branch_wanted.strip("\"")

    with open("{}/suite.{}.status".format(suite.webTopDir, branch), "w") as f:
        f.write("{}; num failed: {}; source hash: {}".format(
            suite.repos[name].name, num_failed, suite.repos[name].hash_current))


    #--------------------------------------------------------------------------
    # generate the master report for all test instances
    #--------------------------------------------------------------------------
    suite.log.skip()
    suite.log.bold("creating suite report...")
    report.report_all_runs(suite, active_test_list)
    
    # delete any temporary directories
    suite.delete_tempdirs()

    def email_developers():
        msg = email.message_from_string(suite.emailBody)
        msg['From'] = suite.emailFrom
        msg['To'] = ",".join(suite.emailTo)
        msg['Subject'] = suite.emailSubject

        server = smtplib.SMTP('localhost')
        server.sendmail(suite.emailFrom, suite.emailTo, msg.as_string())
        server.quit()

    if num_failed > 0 and suite.sendEmailWhenFail and not args.send_no_email:
        suite.log.skip()
        suite.log.bold("sending email...")
        email_developers()


    if suite.slack_post:
        suite.slack_post_it("> test complete, num failed = {}\n{}".format(num_failed, suite.emailBody))

    return num_failed


if __name__ == "__main__":
    n = test_suite(sys.argv[1:])
    sys.exit(n)
