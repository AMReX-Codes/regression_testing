from __future__ import print_function

import datetime
import json
import os
import glob
import shutil
import sys
import test_util
import tempfile as tf

try: from json.decoder import JSONDecodeError
except ImportError: JSONDecodeError = ValueError

DO_TIMINGS_PLOTS = True

try:
    
    import bokeh
    from bokeh.plotting import figure, save, ColumnDataSource
    from bokeh.resources import CDN
    from bokeh.models import HoverTool
    from datetime import datetime as dt
    
except:
    
    try: import matplotlib
    except: DO_TIMINGS_PLOTS = False
    else:
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    
    try: import matplotlib.dates as dates
    except: DO_TIMINGS_PLOTS = False

class Test(object):

    def __init__(self, name):

        self.name = name

        self.log = None

        self.buildDir = ""

        self.extra_build_dir = ""

        self.target = ""

        self.testSrcTree = ""

        self.inputFile = ""
        self.probinFile = ""
        self.auxFiles = []
        self.linkFiles = []

        self.dim = -1
        
        self.run_as_script = ""
        self.script_args = ""
        self.return_code = None

        self.restartTest = 0
        self.restartFileNum = -1

        self._compileTest = 0

        self.selfTest = 0
        self.stSuccessString = ""

        self.debug = 0

        self.acc = 0

        self.useMPI = 0
        self.numprocs = -1

        self.useOMP = 0
        self.numthreads = -1

        self.doVis = 0
        self.visVar = ""

        self._doComparison = True
        self._tolerance = None

        self.analysisRoutine = ""
        self.analysisMainArgs = ""
        self.analysisOutputImage = ""

        self.png_file = None

        self.outputFile = ""
        self.compareFile = ""

        self.compare_file_used = ""

        self.diffDir = ""
        self.diffOpts = ""

        self.addToCompileString = ""
        self.ignoreGlobalMakeAdditions = 0

        self.runtime_params = ""

        self.reClean = 0    # set automatically, not by users

        self.wall_time = 0   # set automatically, not by users
        self.build_time = 0  # set automatically, not by users

        self.nlevels = None  # set but running fboxinfo on the output

        self.comp_string = None  # set automatically
        self.executable = None   # set automatically
        self.run_command = None  # set automatically

        self.job_info_field1 = ""
        self.job_info_field2 = ""
        self.job_info_field3 = ""

        self.has_jobinfo = 0  # filled automatically

        self.backtrace = []   # filled automatically

        self.has_stderr = False # filled automatically

        self.compile_successful = False  # filled automatically
        self.compare_successful = False  # filled automatically
        self.analysis_successful = False # filled automatically

        self.customRunCmd = None

        self.compareParticles = False
        self.particleTypes = ""

        self._check_performance = 0
        self._performance_threshold = 1.2
        self._runs_to_average = 5
        self.past_average = None

        self.keywords = []

    def __lt__(self, other):
        return self.value() < other.value()

    def value(self):
        return self.name

    def find_backtrace(self):
        """ find any backtrace files produced """
        return [ft for ft in os.listdir(self.output_dir)
                if os.path.isfile(ft) and ft.startswith("Backtrace.")]

    def get_compare_file(self, output_dir=None):
        """ Find the last plotfile written.  Note: we give an error if the
            last plotfile is 0.  If output_dir is specified, then we use
            that instead of the default
        """

        if output_dir is None:
            output_dir = self.output_dir   # not yet implemented
            
        if self.run_as_script:
            
            outfile = self.outfile
            filepath = os.path.join(output_dir, outfile)
            
            if not os.path.isfile(filepath) or self.crashed:
                
                self.log.warn("test did not produce any output")
                return ""
                
            else: return outfile

        plts = [d for d in os.listdir(output_dir) if \
                (os.path.isdir(d) and
                 d.startswith("{}_plt".format(self.name))) or \
                (os.path.isfile(d) and
                 d.startswith("{}_plt".format(self.name)) and d.endswith(".tgz"))]

        if len(plts) == 0:
            self.log.warn("test did not produce any output")
            return ""

        plts.sort()
        last_plot = plts.pop()

        if last_plot.endswith("00000"):
            self.log.warn("only plotfile 0 was output -- skipping comparison")
            return ""

        return last_plot

    def measure_performance(self):
        """ returns performance relative to past average, as a tuple of:
            meets threshold, percentage slower/faster, whether slower/faster """

        try:
            ratio = self.wall_time / self.past_average
        except (ZeroDivisionError, TypeError):
            return None, 0.0, "error computing ratio"

        meets_threshold = ratio < self.performance_threshold
        percentage = 100 * (1 - ratio)

        if percentage < 0: compare_str = "slower"
        else: compare_str = "faster"

        return meets_threshold, abs(percentage), compare_str

    #######################################################
    #           Static members and properties             #
    #######################################################

    @property
    def passed(self):
        """ Whether the test passed or not """

        compile = self.compile_successful
        if self.compileTest or not compile: return compile

        compare = not self.doComparison or self.compare_successful
        analysis = self.analysisRoutine == "" or self.analysis_successful
        return compare and analysis
    
    @property
    def crashed(self):
        """ Whether the test crashed or not """
        
        return len(self.backtrace) > 0 or (self.run_as_script and self.return_code != 0)
    
    @property
    def outfile(self):
        """ The basename of this run's output file """
        
        return "{}.run.out".format(self.name)
        
    @property
    def errfile(self):
        """ The basename of this run's error file """
        
        return "{}.err.out".format(self.name)
        
    @property
    def comparison_outfile(self):
        """ The basename of this run's comparison output file """
        
        return "{}.compare.out".format(self.name)

    def record_runtime(self, suite):

        test = self.passed and not self.compileTest
        suite = not suite.args.do_temp_run and not suite.args.make_benchmarks
        return test and suite

    def set_compile_test(self, value):
        """ Sets whether this test is compile-only """

        self._compileTest = value

    def get_compile_test(self):
        """ Returns True if the global --compile_only flag was set or
            this test is compile-only, False otherwise
        """

        return self._compileTest or Test.compile_only

    def set_do_comparison(self, value):
        """ Sets whether this test is compile-only """

        self._doComparison = value

    def get_do_comparison(self):
        """ Returns True if the global --compile_only flag was set or
            this test is compile-only, False otherwise
        """

        return self._doComparison and not Test.skip_comparison

    def get_tolerance(self):
        """ Returns the global tolerance if one was set,
            and the test-specific one otherwise.
        """

        if Test.global_tolerance is None:
            return self._tolerance
        return Test.global_tolerance

    def set_tolerance(self, value):
        """ Sets the test-specific tolerance to the specified value. """

        self._tolerance = value

    def get_check_performance(self):
        """ Returns whether to check performance for this test. """

        return self._check_performance or Test.performance_params

    def set_check_performance(self, value):
        """ Setter for check_performance. """

        self._check_performance = value

    def get_performance_threshold(self):
        """ Returns the threshold at which to warn of a performance drop. """

        if Test.performance_params: return float(Test.performance_params[0])
        elif self._check_performance: return self._performance_threshold
        else: return None

    def set_performance_threshold(self, value):
        """ Setter for performance_threshold. """

        self._performance_threshold = value

    def get_runs_to_average(self):
        """ Returns the number of past runs to include in the running runtime average. """

        if Test.performance_params: return int(Test.performance_params[1])
        elif self._check_performance: return self._runs_to_average
        else: return None

    def set_runs_to_average(self, value):
        """ Setter for runs_to_average. """

        self._runs_to_average = value

    # Static member variables, set explicitly in apply_args in Suite class
    compile_only = False
    skip_comparison = False
    global_tolerance = None
    performance_params = []

    # Properties - allow for direct access as an attribute
    # (e.g. test.compileTest) while still utilizing getters and setters
    compileTest = property(get_compile_test, set_compile_test)
    doComparison = property(get_do_comparison, set_do_comparison)
    tolerance = property(get_tolerance, set_tolerance)
    check_performance = property(get_check_performance, set_check_performance)
    performance_threshold = property(get_performance_threshold, set_performance_threshold)
    runs_to_average = property(get_runs_to_average, set_runs_to_average)

class Suite(object):

    def __init__(self, args):

        self.args = args
        self.apply_args()

        # this will hold all of the Repo() objects for the AMReX, source,
        # and build directories
        self.repos = {}

        self.test_file_path = os.getcwd() + '/' + self.args.input_file[0]

        self.suiteName = "testDefault"
        self.sub_title = ""

        self.sourceTree = ""
        self.testTopDir = ""
        self.webTopDir = ""
        self._noWebDir = False
        self.wallclockFile = "wallclock_history"

        self.useCmake = 0
        self.use_ctools = 1

        self.reportCoverage = args.with_coverage

        # set automatically
        self.covered_frac = None
        self.total = None
        self.covered_nonspecific_frac = None
        self.total_nonspecific = None

        self.source_dir = ""
        self.source_build_dir ="" # Cmake build dir
        self.source_cmake_opts =""
        self.amrex_dir = ""
        self.amrex_install_dir = "" # Cmake installation dir
        self.amrex_cmake_opts = ""

        self.MPIcommand = ""
        self.MPIhost = ""

        self.FCOMP = "gfortran"
        self.COMP = "g++"

        self.add_to_f_make_command = ""
        self.add_to_c_make_command = ""

        self.summary_job_info_field1 = ""
        self.summary_job_info_field2 = ""
        self.summary_job_info_field3 = ""

        self.MAKE = "gmake"
        self.numMakeJobs = 1

        self.reportActiveTestsOnly = 0
        self.goUpLink = 0
        self.lenTestName = 0

        self.sendEmailWhenFail = 0
        self.emailFrom = ""
        self.emailTo = []
        self.emailSubject = ""
        self.emailBody = ""

        self.slack_post = 0
        self.slack_webhookfile = ""
        self.slack_webhook_url = None
        self.slack_channel = ""
        self.slack_username = ""

        self.plot_file_name = "amr.plot_file"

        self.globalAddToExecString = ""

        # this will be automatically filled
        self.extra_src_comp_string = ""

        # delete all plot/checkfiles but the plotfile used for comparison upon
        # completion
        self.purge_output = 0

        self.log = None

        self.do_timings_plots = DO_TIMINGS_PLOTS

        # default branch -- we use this only for display purposes --
        # if the test was run on a branch other than the default, then
        # an asterisk will appear next to the date in the main page
        self.default_branch = "master"

    @property
    def timing_default(self):
        """ Determines the format of the wallclock history JSON file """

        return {"runtimes": [], "dates": []}

    def check_test_dir(self, dir_name):
        """ given a string representing a directory, check if it points to
            a valid directory.  If so, return the directory name """

        dir_name = os.path.normpath(dir_name) + "/"

        if not os.path.isdir(dir_name):
            self.log.fail("ERROR: {} is not a valid directory".format(dir_name))

        return dir_name
        
    def init_web_dir(self, dir_name):
        """
        Sets the suite web directory to dir_name if dir_name is neither null
        nor whitespace, and initializes it to a temporary directory under the
        test directory otherwise.
        """
        
        if not (dir_name and dir_name.strip()):
            
            self.webTopDir = tf.mkdtemp(dir=self.testTopDir) + '/'
            self._noWebDir = True
            
        else:
            
            self.webTopDir = os.path.normpath(dir_name) + '/'
            
        if not os.path.isdir(self.webTopDir):
            
            self.log.fail("ERROR: Unable to initialize web directory to"
                    + " {} - invalid path.".format(self.webTopDir))
                    
    def delete_tempdirs(self):
        """
        Removes any temporary directories that were created during the
        current test run.
        """
        
        if self._noWebDir:
            
            shutil.rmtree(self.webTopDir)

    def get_tests_to_run(self, test_list_old):
        """ perform various tests based on the runtime options to determine
            which of the tests in the input file we run """

        # if we only want to run the tests that failed previously,
        # remove the others
        if self.args.redo_failed or not self.args.copy_benchmarks is None:
            last_run = self.get_last_run()
            failed = self.get_test_failures(last_run)

            test_list = [t for t in test_list_old if t.name in failed]
        else:
            test_list = test_list_old[:]

        # if we only want to run tests of a certain dimensionality, remove
        # the others
        if self.args.d in [1, 2, 3]:
            test_list = [t for t in test_list_old if t.dim == self.args.d]

        # if we specified any keywords, only run those
        if self.args.keyword is not None:
            test_list = [t for t in test_list_old if self.args.keyword in t.keywords]

        # if we are doing a single test, remove all other tests; if we
        # specified a list of tests, check each one; if we did both
        # --single_test and --tests, complain
        if not self.args.single_test == "" and not self.args.tests == "":
            self.log.fail("ERROR: specify tests either by --single_test or --tests, not both")

        if not self.args.single_test == "":
            tests_find = [self.args.single_test]
        elif not self.args.tests == "":
            tests_find = self.args.tests.split()
        else:
            tests_find = []

        if len(tests_find) > 0:
            new_test_list = []
            for test in tests_find:
                _tmp = [o for o in test_list if o.name == test]
                if len(_tmp) == 1:
                    new_test_list += _tmp
                else:
                    self.log.fail("ERROR: {} is not a valid test".format(test))

            test_list = new_test_list

        if len(test_list) == 0:
            self.log.fail("No valid tests defined")

        return test_list

    def get_bench_dir(self):
        bench_dir = self.testTopDir + self.suiteName + "-benchmarks/"
        if not os.path.isdir(bench_dir):
            if not self.args.make_benchmarks is None:
                os.mkdir(bench_dir)
            else:
                self.log.fail("ERROR: benchmark directory, {}, does not exist".format(bench_dir))
        return bench_dir

    def get_wallclock_file(self):
        """ returns the path to the json file storing past runtimes for each test """

        return os.path.join(self.get_bench_dir(), "{}.json".format(self.wallclockFile))

    def make_test_dirs(self):
        os.chdir(self.testTopDir)

        today_date = datetime.date.today()
        today = today_date.__str__()

        # figure out what the current output directory should be
        maxRuns = 100      # maximum number of tests in a given day

        test_dir = today + "/"

        # test output stored in a directory suiteName-tests/2007-XX-XX/
        # make sure that the suiteName-tests directory exists
        if not os.path.isdir(self.testTopDir + self.suiteName + "-tests/"):
            os.mkdir(self.testTopDir + self.suiteName + "-tests/")

        full_test_dir = self.testTopDir + self.suiteName + "-tests/" + test_dir

        if self.args.do_temp_run:
            test_dir = "TEMP_RUN/"
            full_test_dir = self.testTopDir + self.suiteName + "-tests/" + test_dir
            if os.path.isdir(full_test_dir):
                shutil.rmtree(full_test_dir)
        else:
            for i in range(1, maxRuns):
                if not os.path.isdir(full_test_dir): break
                test_dir = today + "-{:03d}/".format(i)
                full_test_dir = self.testTopDir + self.suiteName + "-tests/" + test_dir

        self.log.skip()
        self.log.bold("testing directory is: " + test_dir)
        os.mkdir(full_test_dir)

        # make the web directory -- this is where all the output and HTML will be
        # put, so it is easy to move the entire test website to a different disk
        full_web_dir = "{}/{}/".format(self.webTopDir, test_dir)

        if self.args.do_temp_run:
            if os.path.isdir(full_web_dir):
                shutil.rmtree(full_web_dir)

        os.mkdir(full_web_dir)

        # copy the test file into the web output directory
        shutil.copy(self.test_file_path, full_web_dir)

        self.test_dir = test_dir
        self.full_test_dir = full_test_dir
        self.full_web_dir = full_web_dir

    def get_run_history(self, active_test_list=None, check_activity=True):
        """ return the list of output directories run over the
            history of the suite and a separate list of the tests
            run (unique names) """

        valid_dirs = []
        all_tests = []

        # start by finding the list of valid test directories
        for f in os.listdir(self.webTopDir):

            f_path = os.path.join(self.webTopDir, f)
            # look for a directory of the form 20* (this will work up until 2099
            if f.startswith("20") and os.path.isdir(f_path):

                # look for the status file
                status_file = f_path + '/' + f + '.status'
                if os.path.isfile(status_file):
                    valid_dirs.append(f)

        valid_dirs.sort()
        valid_dirs.reverse()

        # now find all of the unique problems in the test directories
        for d in valid_dirs:

            for f in os.listdir(self.webTopDir + d):
                if f.endswith(".status") and not (f.startswith("20") or f == "branch.status"):
                    index = f.rfind(".status")
                    test_name = f[0:index]

                    if all_tests.count(test_name) == 0:
                        if (not (self.reportActiveTestsOnly and check_activity)) or (test_name in active_test_list):
                            all_tests.append(test_name)

        all_tests.sort()

        return valid_dirs, all_tests

    def get_wallclock_history(self):
        """ returns the wallclock time history for all the valid tests as a dictionary
            of NumPy arrays. Set filter_times to False to return 0.0 as a placeholder
            when there was no available execution time. """

        def extract_time(file):
            """ Helper function for getting runtimes """

            for line in file:

                if "Execution time" in line:
                    # this is of the form: <li>Execution time: 412.930 s
                    return float(line.split(":")[1].strip().split(" ")[0])

                elif "(seconds)" in line:
                    # this is the older form -- split on "="
                    # form: <p><b>Execution Time</b> (seconds) = 399.414828
                    return float(line.split("=")[1])

            raise RuntimeError()

        json_file = self.get_wallclock_file()

        if os.path.isfile(json_file):

            try:
                timings = json.load(open(json_file, 'r'))
                # Check for proper format
                item = next(iter(timings.values()))
                if not isinstance(item, dict): raise JSONDecodeError()
                return timings
            except (IOError, OSError, JSONDecodeError, StopIteration): pass

        valid_dirs, all_tests = self.get_run_history(check_activity=False)

        # store the timings in a dictionary
        timings = dict()

        for dir in valid_dirs:

            # Get status files
            dir_path = os.path.join(self.webTopDir, dir)
            sfiles = glob.glob("{}/*.status".format(dir_path))
            sfiles = list(filter(os.path.isfile, sfiles))

            # Tests that should be counted
            passed = set()

            for i, file in enumerate(map(open, sfiles)):

                contents = file.read()

                if "PASSED" in contents:
                    filename = os.path.basename(sfiles[i])
                    passed.add(filename.split(".")[0])

                file.close()

            for test in filter(lambda x: x in passed, all_tests):

                file = "{}/{}.html".format(dir_path, test)
                try: file = open(file)
                except: continue

                try: time = extract_time(file)
                except RuntimeError: continue

                test_dict = timings.setdefault(test, self.timing_default)
                test_dict["runtimes"].append(time)
                test_dict["dates"].append(dir.rstrip("/"))

                file.close()

        return timings

    def make_timing_plots(self, active_test_list=None, valid_dirs=None, all_tests=None):
        """ plot the wallclock time history for all the valid tests """

        if active_test_list is not None:
            valid_dirs, all_tests = self.get_run_history(active_test_list)
        timings = self.get_wallclock_history()
        
        try: bokeh
        except NameError:
            
            convf = dates.datestr2num
            using_mpl = True
            self.plot_ext = "png"
            
        else:
            
            convf = lambda s: dt.strptime(s, '%Y-%m-%d')
            using_mpl = False
            self.plot_ext = "html"

        def convert_date(date):
            """ Convert to a matplotlib readable date"""

            if len(date) > 10: date = date[:date.rfind("-")]
            return convf(date)
            
        def hover_tool():
            """
            Encapsulates hover tool creation to prevent errors when generating
            multiple documents.
            """
            
            return HoverTool(
                tooltips=[("date", "@date{%F}"), ("runtime", "@runtime{0.00}")],
                formatters={"date": "datetime"})

        # make the plots
        for t in all_tests:

            try: test_dict = timings[t]
            except KeyError: continue

            days = list(map(convert_date, test_dict["dates"]))
            times = test_dict["runtimes"]

            if len(times) == 0: continue

            if using_mpl:
                
                plt.clf()
                plt.plot_date(days, times, "o", xdate=True)

                years = dates.YearLocator()   # every year
                months = dates.MonthLocator()
                years_fmt = dates.DateFormatter('%Y')

                ax = plt.gca()
                ax.xaxis.set_major_locator(years)
                ax.xaxis.set_major_formatter(years_fmt)
                ax.xaxis.set_minor_locator(months)

                plt.ylabel("time (seconds)")
                plt.title(t)

                if max(times) / min(times) > 10.0:
                    ax.set_yscale("log")

                fig = plt.gcf()
                fig.autofmt_xdate()

                plt.savefig("{}/{}-timings.{}".format(self.webTopDir, t, self.plot_ext))
                
            else:
                
                source = ColumnDataSource(dict(date=days, runtime=times))
                
                settings = dict(x_axis_type="datetime")
                if max(times) / min(times) > 10.0: settings["y_axis_type"] = "log"
                plot = figure(**settings)
                plot.add_tools(hover_tool())
                
                plot.circle("date", "runtime", source=source)
                plot.xaxis.axis_label = "Date"
                plot.yaxis.axis_label = "Runtime (s)"
                
                save(plot, resources=CDN,
                        filename="{}/{}-timings.{}".format(self.webTopDir, t, self.plot_ext),
                        title="{} Runtime History".format(t))

    def get_last_run(self):
        """ return the name of the directory corresponding to the previous
            run of the test suite """

        outdir = self.testTopDir + self.suiteName + "-tests/"

        # this will work through 2099
        if os.path.isdir(outdir):
            dirs = [d for d in os.listdir(outdir) if (os.path.isdir(outdir + d) and
                                                      d.startswith("20"))]
            dirs.sort()

            return dirs[-1]
        else:
            return None

    def get_test_failures(self, test_dir):
        """ look at the test run in test_dir and return the list of tests that
            failed """

        cwd = os.getcwd()

        outdir = self.testTopDir + self.suiteName + "-tests/"

        os.chdir(outdir + test_dir)

        failed = []

        for test in os.listdir("."):
            if not os.path.isdir(test): continue

            # the status files are in the web dir
            status_file = "{}/{}/{}.status".format(self.webTopDir, test_dir, test)
            with open(status_file, "r") as sf:
                for line in sf:
                    if line.find("FAILED") >= 0 or line.find("CRASHED") >= 0:
                        failed.append(test)

        os.chdir(cwd)
        return failed

    def make_realclean(self, repo="source"):
        build_comp_string = ""
        if self.repos[repo].build == 1:
            if not self.repos[repo].comp_string is None:
                build_comp_string = self.repos[repo].comp_string

        extra_src_comp_string = ""
        if not self.extra_src_comp_string is None:
            extra_src_comp_string = self.extra_src_comp_string

        cmd = "{} AMREX_HOME={} {} {} realclean".format(
            self.MAKE, self.amrex_dir,
            extra_src_comp_string, build_comp_string)

        test_util.run(cmd)

    def get_comp_string_f(self, test=None, opts="", target="", outfile=None ):
        build_opts = ""
        f_make_additions = self.add_to_f_make_command
        
        if test is not None:
            build_opts += "NDEBUG={} ".format(f_flag(test.debug, test_not=True))
            build_opts += "ACC={} ".format(f_flag(test.acc))
            build_opts += "MPI={} ".format(f_flag(test.useMPI))
            build_opts += "OMP={} ".format(f_flag(test.useOMP))

            if not test.extra_build_dir == "":
                build_opts += self.repos[test.extra_build_dir].comp_string + " "

            if not test.addToCompileString == "":
                build_opts += test.addToCompileString + " "
                
            if test.ignoreGlobalMakeAdditions:
                f_make_additions = ""

        all_opts = "{} {} {}".format(self.extra_src_comp_string, build_opts, opts)

        comp_string = "{} -j{} AMREX_HOME={} COMP={} {} {} {}".format(
            self.MAKE, self.numMakeJobs, self.amrex_dir,
            self.FCOMP, f_make_additions, all_opts, target)

        return comp_string

    def build_f(self, test=None, opts="", target="", outfile=None):
        """ build an executable with the Fortran AMReX build system """
        comp_string = self.get_comp_string_f(test, opts, target, outfile)

        self.log.log(comp_string)
        stdout, stderr, rc = test_util.run(comp_string, outfile=outfile)

        # make returns 0 if everything was good
        if not rc == 0:
            self.log.warn("build failed")

        return comp_string, rc

    def get_comp_string_c(self, test=None, opts="", target="",
                          outfile=None, c_make_additions=None):
        build_opts = ""
        if c_make_additions is None:
            c_make_additions = self.add_to_c_make_command

        if test is not None:
            build_opts += "DEBUG={} ".format(c_flag(test.debug))
            build_opts += "USE_ACC={} ".format(c_flag(test.acc))
            build_opts += "USE_MPI={} ".format(c_flag(test.useMPI))
            build_opts += "USE_OMP={} ".format(c_flag(test.useOMP))
            build_opts += "DIM={} ".format(test.dim)

            if not test.extra_build_dir == "":
                build_opts += self.repos[test.extra_build_dir].comp_string + " "

            if "source" in self.repos:
                if not self.repos["source"].comp_string is None:
                    build_opts += self.repos["source"].comp_string + " "

            if not test.addToCompileString == "":
                build_opts += test.addToCompileString + " "
                
            if test.ignoreGlobalMakeAdditions:
                c_make_additions = ""

        all_opts = "{} {} {}".format(self.extra_src_comp_string, build_opts, opts)

        comp_string = "{} -j{} AMREX_HOME={} {} COMP={} {} {}".format(
            self.MAKE, self.numMakeJobs, self.amrex_dir,
            all_opts, self.COMP, c_make_additions, target)

        return comp_string
    
    def build_c(self, test=None, opts="", target="",
                outfile=None, c_make_additions=None):
        comp_string = self.get_comp_string_c( test, opts, target,
                                              outfile, c_make_additions )
        self.log.log(comp_string)
        stdout, stderr, rc = test_util.run(comp_string, outfile=outfile)

        # make returns 0 if everything was good
        if not rc == 0:
            self.log.warn("build failed")

        return comp_string, rc

    def run_test(self, test, base_command):
        test_env = None
        if test.useOMP:
            test_env = dict(os.environ, OMP_NUM_THREADS="{}".format(test.numthreads))

        if test.useMPI and not test.run_as_script:
            test_run_command = self.MPIcommand
            test_run_command = test_run_command.replace("@host@", self.MPIhost)
            test_run_command = test_run_command.replace("@nprocs@", "{}".format(test.numprocs))
            test_run_command = test_run_command.replace("@command@", base_command)
        else:
            test_run_command = base_command

        outfile = test.outfile
        
        if test.run_as_script: errfile = None
        else: errfile = test.errfile
        
        self.log.log(test_run_command)
        sout, serr, ierr = test_util.run(test_run_command, stdin=True,
                                         outfile=outfile, errfile=errfile,
                                         env=test_env)
        test.run_command = test_run_command
        test.return_code = ierr

    def copy_backtrace(self, test):
        """
        if any backtrace files were output (because the run crashed), find them
        and copy them to the web directory
        """
        backtrace = test.find_backtrace()

        for btf in backtrace:
            ofile = "{}/{}.{}".format(self.full_web_dir, test.name, btf)
            shutil.copy(btf, ofile)
            test.backtrace.append("{}.{}".format(test.name, btf))


    def build_tools(self, test_list):

        self.log.skip()
        self.log.bold("building tools...")
        self.log.indent()

        self.tools = {}

        self.f_compare_tool_dir = "{}/Tools/Plotfile/".format(
            os.path.normpath(self.amrex_dir))

        os.chdir(self.f_compare_tool_dir)

        self.make_realclean(repo="AMReX")

        ftools = ["fcompare", "fboxinfo", "fsnapshot"]
        if any([t for t in test_list if t.tolerance is not None]): ftools.append("fvarnames")
        # Hack to prevent tools from building
        ftools = []

        for t in ftools:
            self.log.log("building {}...".format(t))
            comp_string, rc = self.build_c(target="programs={}".format(t),
                                           opts="DEBUG=FALSE USE_MPI=FALSE USE_OMP=FALSE ",
                                           c_make_additions="")
            if not rc == 0:
                self.log.fail("unable to continue, tools not able to be built")

            exe = test_util.get_recent_filename(self.f_compare_tool_dir, t, ".ex")
            self.tools[t] = "{}/{}".format(self.f_compare_tool_dir, exe)

        self.c_compare_tool_dir = "{}/Tools/Postprocessing/C_Src/".format(
            os.path.normpath(self.amrex_dir))


        if self.use_ctools:
            try:
                os.chdir(self.c_compare_tool_dir)
            except OSError:
                ctools = []
            else:
                ctools = ["particle_compare"]
        else:
            ctools = []

        for t in ctools:
            self.log.log("building {}...".format(t))
            comp_string, rc = self.build_c(opts="DEBUG=FALSE USE_MPI=FALSE ")
            if not rc == 0:
                self.log.fail("unable to continue, tools not able to be built")

            exe = test_util.get_recent_filename(self.c_compare_tool_dir, t, ".exe")

            self.tools[t] = "{}/{}".format(self.c_compare_tool_dir, exe)

        self.log.outdent()

    def slack_post_it(self, message):

        payload = {}

        # make sure there are no quotes in the strings
        payload["channel"] = self.slack_channel.replace('"', '')
        payload["username"] = self.slack_username.replace('"', '')
        payload["text"] = message.replace("'", "")  # apostrophes

        s = json.dumps(payload)
        cmd = "curl -X POST --data-urlencode 'payload={}' {}".format(s, self.slack_webhook_url)
        test_util.run(cmd)

    def apply_args(self):
        """
        makes any necessary adjustments to module settings based on the
        command line arguments supplied to the main module
        """

        args = self.args

        Test.compile_only = args.compile_only
        Test.skip_comparison = args.skip_comparison
        Test.global_tolerance = args.tolerance
        Test.performance_params = args.check_performance

    #######################################################
    #        CMake utilities                              #
    #######################################################
    def cmake_config( self, name, path, configOpts="",  install = 0, env = None):
        "Generate Cmake configuration"

        self.log.outdent()
        self.log.skip()
        self.log.bold("configuring " + name +  " build...")
        self.log.indent()

        # Setup dir names
        builddir   = path + 'builddir'
        if install:
            installdir = path + 'installdir'
        else:
            installdir = None

        # Define enviroment
        ENV = {}
        ENV =  dict(os.environ) # Copy of current enviroment
        ENV['FC']  = self.FCOMP
        ENV['CXX'] = self.COMP

        if env is not None: ENV.update(env)

        # remove build and installation directories if present and re-make them
        if os.path.isdir(builddir):
            shutil.rmtree(builddir)
        self.log.log("mkdir " + builddir)
        os.mkdir(builddir)

        if install:
            if os.path.isdir(installdir):
                shutil.rmtree(installdir)
            self.log.log("mkdir " + installdir)
            os.mkdir(installdir)

        # Logfile
        coutfile = '{}{}.cmake.log'.format( self.full_test_dir, name )

        # Run cmake
        cmd = 'cmake {} -H{} -B{} '.format(configOpts, path, builddir)
        if install:
            cmd += '-DCMAKE_INSTALL_PREFIX:PATH='+installdir

        self.log.log(cmd)
        stdout, stderr, rc = test_util.run(cmd, outfile=coutfile, env=ENV)

        # Check exit condition
        if not rc == 0:
            errstr  = "\n \nERROR! Cmake configuration failed for " + name + " \n"
            errstr += "Check " + coutfile + " for more information."
            sys.exit(errstr)

        return builddir, installdir


    def cmake_clean( self, name, path ):
        "Clean Cmake build and install directories"

        self.log.outdent()
        self.log.skip()
        self.log.bold("cleaning " + name +  " Cmake directories...")
        self.log.indent()

        # Setup dir names
        builddir   = path + 'builddir'
        installdir = path + 'installdir'

        # remove build and installation directories if present
        if os.path.isdir(builddir):
            shutil.rmtree(builddir)

        if os.path.isdir(installdir):
                shutil.rmtree(installdir)

        return

    def cmake_build( self, name, target, path, opts = '', env = None, outfile = None ):
        "Build target for a repo configured via cmake"

        self.log.outdent()
        self.log.skip()
        self.log.bold("building " + name +  "...")
        self.log.indent()

        # Set enviroment
        ENV =  dict(os.environ) # Copy of current enviroment
        if env is not None: ENV.update(env)

        if outfile is not None:
            coutfile = outfile
        else:
            coutfile = '{}{}.{}.make.log'.format( self.full_test_dir, name, target )

        cmd = '{} -j{} {} {}'.format( self.MAKE, self.numMakeJobs, opts, target )
        self.log.log(cmd)
        stdout, stderr, rc = test_util.run(cmd, outfile=coutfile, cwd=path, env=ENV )

        # make returns 0 if everything was good
        if not rc == 0:
            self.log.warn("build failed")

        comp_string = cmd

        return rc, comp_string



    def build_test_cmake(self, test, opts="",  outfile=None):
        """ build an executable with CMake build system """

        env = {"AMREX_HOME":self.amrex_install_dir}

        rc, comp_string = self.cmake_build( name    = test.name,
                                            target  = test.target,
                                            path    = self.source_build_dir,
                                            opts    = opts,
                                            env     = env,
                                            outfile = outfile)

        # make returns 0 if everything was good
        if rc == 0:
            # Find location of executable
            for root, dirnames, filenames in os.walk(self.source_build_dir):
                if test.target in filenames:
                    path_to_exe = os.path.join(root, test.target)
                    break

            # Copy and rename executable to test dir
            shutil.move("{}".format(path_to_exe),
                        "{}/{}/{}.ex".format(self.source_dir,test.buildDir,test.name))
        else:
          self.log.warn("build failed")


        return comp_string, rc



def f_flag(opt, test_not=False):
    """ convert a test parameter into t if true for the Fortran build system """
    if test_not:
        if opt: return " "
        else: return "t"
    else:
        if opt: return "t"
        else: return " "

def c_flag(opt, test_not=False):
    """ convert a test parameter into t if true for the Fortran build system """
    if test_not:
        if opt: return "FALSE"
        else: return "TRUE"
    else:
        if opt: return "TRUE"
        else: return "FALSE"
