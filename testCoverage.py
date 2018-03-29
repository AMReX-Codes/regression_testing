'''
Start Date: 02/21/18

Author: Patrick Payne

Purpose: Check all of the tests for MAESTRO to see if every parameter
          has been tested at a value different from the default value

MAESTRO returns a maestro-overview.out file that lists all of the runtime parameters
that were used in the simulation. The values that were set different from the default
values are marked with a [*]. This is the feature that we are looking for to determine
if the quantity is covered. 

First read the list of all of the possible parameters and then compare and strike the 
list items as we progress through the parameters that were tested. Finally, output a 
coverage file that lists the parameters that were covered and the parameters that were 
not covered in the test suite.


+Ignore Problem Specific Parameters

There should be a 276 total parameters, this include the problem specific parameters
'''


import os
import sys
import re as re


def main():
    #Put the script in the directory where the tests are and execute it in there as your CWD
    
    filePaths = getFiles() #gets the paths of the files of interest

    covered = []           #initialize lists
    noCover = []
    ignore = []
    ignoremaster = []
    coveredNoSpecific = []
    noCoverNoSpecific = []
    allparams = []
    ALL = []
    
    for i in range(0,len(filePaths)):
                   
        startline = get_startline(filePaths[i])

        coveredTemp, noCoverTemp, ALL = list_parameters(filePaths[i],startline,ALL)

        if i == 0: noCover = noCoverTemp #initializing noCover
        if i == 0: covered = coveredTemp #initializing covered

        covered, noCover, ignore, ignoremaster, allparams= BuildMaster(coveredTemp,noCoverTemp,covered,noCover,ignore,ignoremaster,allparams)
        
        
    #BuildMaster needs to be executed one more time than the number of cycles in the loop to complete the ignore list
    covered, noCover, ignore, ignoremaster, allparams= BuildMaster(coveredTemp,noCoverTemp,covered,noCover,ignore,ignoremaster,allparams)

    coveredFrac, noCoverFrac = getFrac(covered,noCover)
    OutputCoverage("Coverage.out",covered,noCover,coveredFrac,noCoverFrac)

    
    coveredNoSpecific, noCoverNoSpecific = RemoveSpecificParams(covered,noCover,ignore)
    coveredNoSpecificFrac, noCoverNoSpecificFrac = getFrac(coveredNoSpecific,noCoverNoSpecific)
    OutputCoverage("Coverage-NoSpecific.out",coveredNoSpecific,noCoverNoSpecific,coveredNoSpecificFrac,noCoverNoSpecificFrac,specific = ignore)
    
def get_startline(datafile):
    ''' This routine finds the line number where the list of runtime parameters begins'''

    startline = 0        # The line where the Runtime Parameter Information begins
    counter = 0          # Used to keep track of the line to determine startline
    
    # Finds the Runtime Section and claculates the startline
    with open(datafile,mode='r') as datafile:
        for line in datafile:
            if "Runtime Parameter Information" in line:
                startline = counter + 3 # start line of parameter lists when the first line of the file is line 1
                break
            else:
                counter = counter + 1

                
                # Checks to see if the startline has been found, else it will stop
        if startline <= 0:
            sys.exit("Startline was not identified")
        else:
            datafile.close()
            return startline;

def list_parameters(datafile,startline,ALL):
    '''This routine finds the parameters that have been covered by the test suite and
       those that haven't been covered by the test suite and outputs two lists, one
       for each type of parameter, Covered and NoCover'''

    covered = []     # List to store the names of the covered parameters
    noCover = []     # List to store the names of the non-covered parameters

    with open(datafile,mode='r') as datafile:
        for i, line in enumerate(datafile):
            if i <= startline:
                # ignores lines that are before the Runtime Parameter Information
                pass
            else:
               if r'[*]' in line:
                   # singles out the covered parameters and writes their names
                   parameter = re.split(r' +', line)
                   if parameter:
                       temp = parameter[2]
                       covered.append(temp)
               else:
                   # takes the rest of the parameters (not covered) and writes their names
                   parameterNoCheck = re.split(r' +', line)
                   if parameterNoCheck and parameterNoCheck[1] != "Restart":
                       noCover.append(parameterNoCheck[1])
                       

    datafile.close()

    ALL = covered+noCover+ALL
    
    return covered, noCover, ALL


def BuildMaster(coveredTemp,noCoverTemp,covered,noCover,ignore,ignoremaster,allparams):
    #updates the master list of covered and not covered variables

        #handles the set of noCover parameters for a test    
    for i in range(0,len(noCoverTemp)):

        if noCoverTemp[i] in ignore:
            ignore.remove(noCoverTemp[i])
        elif noCoverTemp[i] not in ignoremaster:
            ignore.append(noCoverTemp[i])
            ignoremaster.append(noCoverTemp[i])
        else:
            pass

        if noCoverTemp[i] not in (noCover or Covered):
            noCover.append(noCoverTemp[i])
        else:
            pass
        
        if noCoverTemp[i] not in allparams:
            allparams.append(noCoverTemp[i])
        else:
            pass

        #handles the set of covered parameters for a test
    for i in range(0,len(coveredTemp)):

        if coveredTemp[i] in ignore:
            ignore.remove(coveredTemp[i])
        elif coveredTemp[i] not in ignoremaster:
            ignore.append(coveredTemp[i])
            ignoremaster.append(coveredTemp[i])
        else:
            pass

        
        if coveredTemp[i] in covered:
            pass
        else:
            #adds newly covered parameters
            covered.append(coveredTemp[i])

        if coveredTemp[i] in (noCover or covered):
            #removes newly covered parameters
            noCover.remove(coveredTemp[i])
        else:
            pass

        if coveredTemp[i] not in allparams:
            allparams.append(coveredTemp[i])


        #Deals with potential duplicates
    for i in range(0,len(covered)):
        if covered[i] in noCover:
            noCover.remove(covered[i])
        else:
            pass


        #removal of empty lines
    try:
        covered.remove("\n")
    except ValueError:
        pass
    try:
        noCover.remove("\n")
    except ValueError:
        pass



        
        
    return covered, noCover, ignore, ignoremaster, allparams
        
def RemoveSpecificParams(covered,noCover,ignore):

    coveredTemp = covered
    noCoverTemp = noCover
    
    for i in range(0,len(ignore)):

        if ignore[i] in noCover:
            noCoverTemp.remove(ignore[i])
        else:
            pass

        
        if ignore[i] in covered:
            coveredTemp.remove(ignore[i])
        else:
            pass

           
    return coveredTemp, noCoverTemp
    
def getFiles():
    #returns the absolute paths of all maestro-overview.out files
    
    data = os.getcwd()      #determines current working directory, which should be the directory
                            # of the most recent test

    Dirs = os.listdir(data) #determines tests in the most recent test

    AbsDirs = []            #initialize list
    filepaths=[]
    
    filename = 'maestro-overview.out' #the file that we are interested in reading
    
    for i in range(0,len(Dirs)):
        #gets absolute path to the directories

        AbsDirs.append(os.path.join(data,Dirs[i]))
        
    for i in range(0,len(AbsDirs)):
        #checks if file of interest is in a directory
        
        fileHere = os.path.join(AbsDirs[i],filename)

        
        if os.path.isfile(fileHere):
            #if it is in the directory then that path is added to the list of files
            
            filepaths.append(os.path.join(AbsDirs[i],filename))

        else:
            pass


    return filepaths   #list of directories with maestro-overview.out

def getFrac(covered,noCover):
    #determines the percentage of the parameters that were covered by the test suite

    numCovered = len(covered)
    numNoCover = len(noCover)

    total = numCovered + numNoCover + 0.0

    coveredFrac = numCovered / total

    noCoverFrac = numNoCover / total

    
    return coveredFrac, noCoverFrac


def OutputCoverage(outputname, covered, noCover,coveredFrac,noCoverFrac,specific=[]):
        
    with open(outputname,mode='w') as coverage:
        # Makes a file and to list the parameters that were not covered by the tests
        coverage.write("================================================== \n")
        coverage.write("Parameters that were not covered: \n")
        coverage.write("================================================== \n \n")
        for i in range(0,len(noCover)):
            coverage.write(noCover[i] + "\n")
        coverage.write("================================================== \n")
        coverage.write("Percentage of parameters that were not covered: {} \n".format(noCoverFrac))
        coverage.write("Number of parameters not covered: {} \n".format(len(noCover)))
        coverage.write("Number of parameters covered: {} \n".format(len(covered)))
        coverage.write("Total number of parameters: {} \n".format(len(covered)+len(noCover)))
        if len(specific) != 0: coverage.write("Number of parameters ignored as problem specific parameters: {} \n".format(len(specific)))

#    print("{}".format(noCover))

def removeDuplicates(allparams):
    #removes all of the duplicate parameters and provides it as a set and gives its length

    return list(set(allparams)), len(list(set(allparams)))

if __name__ == '__main__':
    main();
