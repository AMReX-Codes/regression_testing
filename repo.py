"""This module is used to handle all of the git operations for the
test suite"""

import os
import shutil
import test_util

class Repo:
    """ a simple class to manage our git operations """
    def __init__(self, suite, directory, name,
                 branch_wanted=None, pr_wanted=None, hash_wanted=None,
                 build=0, comp_string=None):

        self.suite = suite
        self.dir = directory
        self.name = name
        self.branch_wanted = branch_wanted
        self.pr_wanted = pr_wanted
        self.hash_wanted = hash_wanted

        self.build = build   # does this repo contain build directories?
        self.comp_string = comp_string   # environment vars needed to build

        # for storage
        self.branch_orig = None
        self.hash_current = None

        self.update = True
        if hash_wanted:
            self.update = False

    def get_branch_name(self):
        """for descriptive purposes, return the name of the branch we will
        use.  This could be a PR branch that was fetched"""
        if self.pr_wanted is not None:
            return "pr-{}".format(self.pr_wanted)
        elif self.branch_wanted is not None:
            return self.branch_wanted.strip("\"")

        return None

    def git_update(self):
        """ Do a git update of the repository.  If githash is not empty, then
            we will check out that version instead of git-pulling. """

        os.chdir(self.dir)

        # find out current branch so that we can go back later if we need.
        stdout0, _, _ = test_util.run("git rev-parse --abbrev-ref HEAD")
        self.branch_orig = stdout0.rstrip('\n')

        # just in case the branch we want is not in the local repo
        # yet, start out with a git fetch
        self.suite.log.log("git fetch in {}".format(self.dir))
        _, _, rc = test_util.run("git fetch", stdin=True)

        if rc != 0:
            self.suite.log.fail("ERROR: git fetch was unsuccessful")

        # if we need a special branch, hash or are working on a PR, check it out now
        if self.pr_wanted is not None:
            self.suite.log.log("fetching PR {}".format(self.pr_wanted))
            _, _, rc = test_util.run("git fetch origin pull/{}/head:pr-{}".format(
                self.pr_wanted, self.pr_wanted), stdin=True)
            if rc != 0:
                self.suite.log.fail("ERROR: git fetch was unsuccessful")

            self.suite.log.log("checking out pr-{}".format(self.pr_wanted))
            _, _, rc = test_util.run("git checkout pr-{}".format(self.pr_wanted), stdin=True)
            if rc != 0:
                self.suite.log.fail("ERROR: git checkout was unsuccessful")

        elif self.hash_wanted is not None:
            self.suite.log.log("git checkout {} ".format(self.hash_wanted))
            _, _, rc = test_util.run("git checkout {}".format(self.hash_wanted),
                                         stdin=True, outfile="git.{}.out".format(self.name))

            if rc != 0:
                self.suite.log.fail("ERROR: git update was unsuccessful")

        elif self.branch_orig != self.branch_wanted:
            self.suite.log.log("git checkout {} in {}".format(self.branch_wanted, self.dir))
            _, _, rc = test_util.run("git checkout {}".format(self.branch_wanted),
                                     stdin=True)

            if rc != 0:
                self.suite.log.fail("ERROR: git checkout was unsuccessful")

        else:
            self.branch_wanted = self.branch_orig

        # get up to date on our branch
        if self.pr_wanted is None:
            if self.hash_wanted == "" or self.hash_wanted is None:
                self.suite.log.log("'git pull' in {}".format(self.dir))

                _, _, rc = test_util.run("git pull", stdin=True,
                                         outfile="git.{}.out".format(self.name))

            shutil.copy("git.{}.out".format(self.name), self.suite.full_web_dir)

    def save_head(self):
        """Save the current head of the repo"""

        os.chdir(self.dir)

        self.suite.log.log("saving git HEAD for {}/".format(self.name))

        stdout, _, _ = test_util.run("git rev-parse HEAD",
                                     outfile="git.{}.HEAD".format(self.name))

        self.hash_current = stdout
        shutil.copy("git.{}.HEAD".format(self.name), self.suite.full_web_dir)

    def make_changelog(self):
        """ generate a ChangeLog git repository, and copy it to the
            web directory"""

        os.chdir(self.dir)

        self.suite.log.log("generating ChangeLog for {}/".format(self.name))

        test_util.run("git log --name-only",
                      outfile="ChangeLog.{}".format(self.name), outfile_mode="w")
        shutil.copy("ChangeLog.{}".format(self.name), self.suite.full_web_dir)

    def git_back(self):
        """ switch the repo back to its original branch """

        os.chdir(self.dir)
        self.suite.log.log("git checkout {} in {}".format(self.branch_orig, self.dir))

        _, _, rc = test_util.run("git checkout {}".format(self.branch_orig),
                                 stdin=True, outfile="git.{}.out".format(self.name))

        if rc != 0:
            self.suite.log.fail("ERROR: git checkout was unsuccessful")

        # if we were working on a PR, delete the temporary branch, since we can't pull on it
        if self.pr_wanted is not None:
            self.suite.log.log("removing pr-{}".format(self.pr_wanted))
            _, _, rc = test_util.run("git branch -D pr-{}".format(self.pr_wanted), stdin=True)

        if rc != 0:
            self.suite.log.fail("ERROR: git branch deletion was unsuccessful")
