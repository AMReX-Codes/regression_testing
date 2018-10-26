=====================
Configuration Options
=====================

Version Control
===============

The toolkit interfaces with Git to provide automated version control operations.
Repository settings may be configured with the following settings in the .ini file
supplied to the main script:

  * ``dir``: The absolute path to the repository directory. This is the only
    required parameter.

  * ``branch``: The git branch to switch to before pulling from the remote or
    checking out a particular version.
  
  * ``hash``: If specified, the toolkit will checkout the version matching the
    hash instead of pulling from the remote.
  
  * ``build``: Should be specified if the repository will serve as a build
    directory for test problems.
  
  * ``comp_string``: A list of any additional environment variables needed
    by the build system.
  
Compilation
===========

Execution
=========
