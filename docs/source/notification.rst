====================
Notification Options
====================

E-mail
======

To receive e-mail notification when tests fail, add ``sendEmailWhenFail = 1``
to the [main] section of the configuration file, and set ``emailTo`` to the
email address to send to and ``emailBody`` to the desired contents.

E-mail notification may be shut off for a single run with the --send_no_email
command line flag, which overrides the configuration file setting.

Slack
=====
