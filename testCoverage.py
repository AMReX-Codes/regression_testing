'''
Start Date: 02/21/18

Author: Patrick Payne

Purpose: Check all of the tests for MAESTRO or CASTRO to see if every
         parameter has been tested at a value different from the 
         default value

In order for this script to function: the output of the tests that it is 
 looking at should be in a form similar to what is shown below:

[START EXAMPLE]

===============================================================================
 Runtime Parameter Information
===============================================================================
[*] indicates overridden default
[*]             parameter_alpha = 1.000
                  parameter_one = F

[END EXAMPLE]

The '[*]' can be preceeded by a space, as is done in MAESTRO (04/24/18), but
 this is not necessary. The script searches for the keyword "Parameter" in
 to begin reading the parameters immediately following the line "[*] indicates
 overridden default" and so will expect the barrier line and that line as well.

As for the form of the tests, the produce plot files should be compressed in a 
 tarfile (".tgz"). This tarfile contains a job_info file where all of the
 runtime parameters that were used in the simulation are listed, in the form 
 that was expressed above. The values that were set different from the default
 values are marked with a [*]. This is the feature that we are looking for to 
 determine if the quantity is covered. 

The basic function of the script is as follows:
 1) All of the test directories are recorded
 2) These directories are checked for a file with the extension ".tgz"
 3) If the file is present, the job_info file is extracted
 4) The parameters are then read from each job_info file
 5) The parameters that occured with a [*] are recorded as covered and the
    others are recorded as not_covered. All duplicates are removed
 6) The problem specific parameters (only used in one simulation) are recorded
 7) The coverage fractions are calculated
 8) The coverage reports are constructed with the list of parameters that were
    not covered, the fraction of total parameters that were covered, and the
    total number of parameters recorded.

Output: Two ".out" files, one that includes any problem specific parameters
 (parameters that are only appear in one test) and one that excludes these
 parameters. The are titled "Coverage.out" and "Coverage-NoSpecific.out",
 respectively.
 
MAESTRO: There should be ~260 total parameters, this includes the problem 
         specific parameters.

CASTRO: There should be ~140 total parameters, this includes the problem
        specific parameters.

Placement: Place the script in the directory where the tests are and execute
           it in there as your CWD

DEVELOPMENT: Add feature for user to specify the test directory on command line

'''


import os
import re as re
import sys
import tarfile

def main():

    # Gets the paths of the files of interest
    file_paths = get_files()  

    # Initialize lists
    covered = []           
    no_cover = []
    ignore = []
    ignore_master = []
    covered_no_specific = []
    no_cover_no_specific = []
    all_params = []
    All = []
    
    for i in range(0, len(file_paths)):
                   
        start_line = get_start_line(file_paths[i])

        covered_temp,  no_cover_temp, All = list_parameters(file_paths[i],
                                                            start_line, All)

        if i == 0: no_cover = no_cover_temp   # Initializing no_cover
        if i == 0: covered = covered_temp     # Initializing covered

        covered, no_cover, ignore, ignore_master, all_params = build_master(
            covered_temp, no_cover_temp, covered,
            no_cover, ignore, ignore_master, all_params)

    All = remove_duplicates(All)
    # build_master needs to be executed one more time than the number of cycles
    # in the loop to complete the ignore list
    covered, no_cover, ignore, ignore_master, all_params = build_master(
        covered_temp, no_cover_temp, covered, no_cover,
        ignore, ignore_master, all_params)

    covered_Frac, no_cover_Frac = get_frac(covered,no_cover)
    output_coverage("Coverage.out", covered, no_cover, covered_Frac,
                    no_cover_Frac)

    covered_no_specific, no_cover_no_specific = remove_specific_params(covered,
                                                                       no_cover,
                                                                       ignore)
    covered_no_specificFrac, no_cover_no_specificFrac = get_frac(
        covered_no_specific, no_cover_no_specific)
    output_coverage("Coverage-NoSpecific.out", covered_no_specific,
                    no_cover_no_specific, covered_no_specificFrac,
                    no_cover_no_specificFrac, specific = ignore)

    clean(file_paths)
    
def get_start_line(data_file):
    # This routine finds the line number where the list of runtime
    # parameters begins

    
    # The line where the Runtime Parameter Information begins
    start_line = 0
    # Used to keep track of the line to determine start_line
    counter = 0
    
    # Finds the Runtime Section and claculates the start_line
    with open(data_file, mode='r') as data_file:
        for line in data_file:
            if "Parameter" in line:
                # Start line of parameter lists when the first line of
                # the file is line 1
                start_line = counter + 3
                break
            else:
                counter = counter + 1

         # Checks to see if the start_line has been found, else it will stop
        if start_line <= 0:
            print(data_file)
            sys.exit("Start_Line was not identified")
        else:
            data_file.close()
            return start_line;

        
def list_parameters(data_file, start_line, All):
    # This routine finds the parameters that have been covered by the test suite
    # and those that haven't been covered by the test suite and outputs two
    # lists, one for each type of parameter, covered and no_cover

    
    covered = []      # List to store the names of the covered parameters
    no_cover = []     # List to store the names of the non-covered parameters

    with open(data_file, mode='r') as data_file:
        for i, line in enumerate(data_file):
            if i <= start_line:
                # Ignores lines that are before the Runtime Parameter Information
                pass
            else:
               if r'[*]' in line:
                   # Singles out the covered parameters and writes their names
                   parameter = re.split(r' +', line.replace("[*]"," "))
                   if parameter:
                       temp = parameter[1]
                       covered.append(temp)
               else:
                   # Takes the rest of the parameters (not covered) and writes their names
                   parameter_no_check = re.split(r' +', line)
                   if parameter_no_check and parameter_no_check[1] != "Restart":
                       no_cover.append(parameter_no_check[1])
                       
    data_file.close()
    All = covered+no_cover+All
    return covered, no_cover, All


def build_master(covered_temp, no_cover_temp, covered, no_cover, ignore,
                 ignore_master, all_params):
    # Updates the master list of covered and not covered variables.

    
    # Handles the set of no_cover parameters for a test    
    for i in range(0, len(no_cover_temp)):

        if no_cover_temp[i] in ignore:
            ignore.remove(no_cover_temp[i])
        elif no_cover_temp[i] not in ignore_master:
            ignore.append(no_cover_temp[i])
            ignore_master.append(no_cover_temp[i])
        else:
            pass

        if no_cover_temp[i] not in (no_cover or Covered):
            no_cover.append(no_cover_temp[i])
        else:
            pass
        
        if no_cover_temp[i] not in all_params:
            all_params.append(no_cover_temp[i])
        else:
            pass

    # Handles the set of covered parameters for a test
    for i in range(0, len(covered_temp)):

        if covered_temp[i] in ignore:
            ignore.remove(covered_temp[i])
        elif covered_temp[i] not in ignore_master:
            ignore.append(covered_temp[i])
            ignore_master.append(covered_temp[i])
        else:
            pass
        
        if covered_temp[i] in covered:
            pass
        else:
            # Adds newly covered parameters
            covered.append(covered_temp[i])

        if covered_temp[i] in (no_cover or covered):
            # Removes newly covered parameters
            no_cover.remove(covered_temp[i])
        else:
            pass

        if covered_temp[i] not in all_params:
            all_params.append(covered_temp[i])

    # Deals with potential duplicates
    for i in range(0, len(covered)):
        if covered[i] in no_cover:
            no_cover.remove(covered[i])
        else:
            pass

    # Removal of empty lines
    try:
        covered.remove("\n")
    except ValueError:
        pass
    try:
        no_cover.remove("\n")
    except ValueError:
        pass
        
    return covered, no_cover, ignore, ignore_master, all_params


def remove_specific_params(covered, no_cover, ignore):
    # Determines the parameters that are specific to some of the
    # tests in the suit.

    
    covered_temp = covered
    no_cover_temp = no_cover
    
    for i in range(0, len(ignore)):

        if ignore[i] in no_cover:
            no_cover_temp.remove(ignore[i])
        else:
            pass

        
        if ignore[i] in covered:
            covered_temp.remove(ignore[i])
        else:
            pass
           
    return covered_temp, no_cover_temp


def get_files():
    # Returns the absolute paths of all maestro-overview.out files.
    # The argunemnt is the name of the file that we are interested
    # in reading.

    
    # Determines current working directory, which should be the directory
    # of the most recent test.
    data = os.getcwd()
    
    # Determines tests in the most recent test
    dirs = []
    dirs = [ d for d in os.listdir(data) if os.path.isdir(d) ]

    abs_dirs = []
    file_paths = []

    for i in range(0, len(dirs)):
        # Gets absolute path to the directories
        abs_dirs.append(os.path.join(data, dirs[i]))

        # Gets the job_info files from .tgz files
    for i in range(0, len(abs_dirs)):
        for file in os.listdir(abs_dirs[i]):
            # Finds the tar files and extracts only job_info file
            if file.endswith(".tgz"):
                tmp = os.path.join(abs_dirs[i], file)
                file_name = os.path.join(data,
                                         os.path.splitext(file)[0])
                # Extracts the job_info file
                tarfile.open(tmp).extract(os.path.splitext(file)[0]
                                          +"/job_info")
                file_name = file_name+"/job_info"
                
                file_here = os.path.join(abs_dirs[i], file_name)
                file_paths.append(file_here)

    # List of directories with file_name (e.g. job_info)
    return file_paths


def get_frac(covered, no_cover):
    # Determines the percentage of the parameters that were covered
    # by the test suite

    
    num_covered = len(covered)
    num_no_cover = len(no_cover)

    total = num_covered + num_no_cover

    covered_frac = num_covered / float(total)

    no_cover_frac = num_no_cover / float(total)
    
    return covered_frac, no_cover_frac


def output_coverage(output_name, covered, no_cover, covered_frac,
                    no_cover_frac, specific = []):
    # Prints the results of the coverage tests to coverage files

    
    with open(output_name, mode='w') as coverage:
        # Makes a file and to list the parameters that were not covered
        # by the tests
        coverage.write("================================================== \n")
        coverage.write("Parameters that were not covered: \n")
        coverage.write("================================================== \n")

        for i in range(0, len(no_cover)):
            coverage.write(no_cover[i] + "\n")

        coverage.write("================================================== \n")
        coverage.write(
            "Coverage: {0:5.2f}% \n"
            .format(covered_frac*100))
        coverage.write("Total number of parameters: {} \n"
                       .format(len(covered)+len(no_cover)))
        coverage.write("Number of parameters covered: {} \n"
                       .format(len(covered)))
        coverage.write("Number of parameters not covered: {} \n"
                       .format(len(no_cover)))
        if len(specific) != 0:
            coverage.write(
                "Number of ignored problem specific parameters: {}\n"
                .format(len(specific)))


def remove_duplicates(all_params):
    # Removes all of the duplicate parameters and provides it as a set
    # and gives its length


    return list(set(all_params)), len(list(set(all_params)))

def clean(file_paths):
    # Removes all of the files and directories created to produce the
    # coverage reports, but it will not delete the coverage reports


    for i in range(0,len(file_paths)):
        
        os.remove(file_paths[i])
        directory = file_paths[i].replace("/job_info","")
        os.rmdir(directory)


if __name__ == '__main__':
    main()
