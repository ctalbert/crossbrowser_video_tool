# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla cross browser video automation tool.
#
# The Initial Developer of the Original Code is
# Clint Talbert.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#  Clint Talbert <cmtalbert@gmail.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
from time import sleep
import subprocess
import os
import optparse
import sys
import ConfigParser
import devicemanagerADB

# Global settings that should be changed or overrided with command line
# parameters.
URL ="file:///mnt/sdcard/startup/m.twitter.com/twitter.com/toptweets/favorites3.html#"

browsermap = {'opera': 'com.opera.browser/com.opera.Opera',
              'android':'com.android.browser/.BrowserActivity',
              'dolphin':'mobi.mgeek.TunnyBrowser/.BrowserActivity',
              'fennec-native': 'org.mozilla.fennec/.App',
              'fennec-xul': 'org.mozilla.fennec/.App'}

# This class just handles ensuring all our options are sane
class StartupOptions(optparse.OptionParser):
    def __init__(self, configfile=None, **kwargs):
        optparse.OptionParser.__init__(self, **kwargs)
        defaults = {}

        self.add_option("--runs", action="store", dest="iterations",
                        help="Number of iterations to run the specific browser, defaults to 19")
        defaults["iterations"] = 19

        self.add_option("--pause", action="store", dest="pause_length",
                         help="Length in seconds of pause between runs, default is  15s")
        defaults["pause_length"] = 15

        self.add_option("--preptime", action="store", dest="flash_length",
                        help="Length in seconds to show settings page before \
                              starting browser, defaults to 5s")

        defaults["flash_length"] = 5

        self.add_option("--url", action="store", dest="url", type="string",
                         help="Full URL to page to open defaults to %s" % URL)
        defaults["url"] = URL

        self.add_option("--apk", action="store", dest="apk", type="string",
                         help="Path to apk to install before running (optional)")
        defaults["apk"] = None

        self.add_option("--sdk", action="store", dest="sdk", type="string",
                         help="Full path to android-sdk directory defaults to \
                               ANDROID_SDK environment variable if set")
        if "ANDROID_SDK" in os.environ:
            defaults["sdk"] = os.environ["ANDROID_SDK"]
        else:
            defaults["sdk"] = None

        self.add_option("--browser", action="store", dest="browser", type="string",
                         help="Name of browser to run - either dolphin, \
                         fennec-native, fennec-xul, android, opera, defaults \
                         to fennec-native")
        defaults["browser"] = "fennec-native"

        self.add_option("--timecmd", action="store", dest="timecmd", type="string",
                        help="Path to timecmd, defaults to local directory")
        defaults["timecmd"] = os.path.join(os.getcwd(), "time")

        self.add_option("--script", action="store", dest="script", type="string",
                        help="Script to run automation defaults to local directory")
        defaults["script"] = os.path.join(os.getcwd(), "runtime.sh")

        self.add_option("--testroot", action="store", dest="testroot", type="string",
                        help="Area to copy scripts etc to phone defaults to \
                             /mnt/sdcard/startup")
        defaults["testroot"] = "/mnt/sdcard/startup"

        self.add_option("--read_length", action="store", dest="read_length", type="string",
                        help="Time to let numbers sit on screen for video, defaults to 10s")
        defaults["read_length"] = 10

        self.set_defaults(**defaults)

        usage = """\
python runstartuptest.py --url=<url>

You can test either specify an apk to install.  The code will uninstall
org.mozilla.fennec and install the apk you provide.  After the test, it will
uninstall org.mozilla.fennec once more.  This way you can test both native
fennec and xul fennec.  The browser name to browser intent mapping is at the
top of this file and should be reviewed before use.

Also, if you don't want to type in the URL you can set that at the top of the
file and then you do not have to specify the --url parameter.  However, you
MUST ENSURE the URL exists before running the application.
"""
        self.set_usage(usage)

    def verify_options(self, options):

        if (not os.path.exists(options.sdk) or
            not os.path.exists(os.path.join(options.sdk, "platform-tools", "adb"))):
            print "Your sdk setting is incorrect. Verify the ANDROID_SDK points \
                   to the root of your sdk and the sdk is installed properly."
            print "Your sdk path is set to: %s" % options.sdk
            return False

        if options.apk and not os.path.exists(options.apk):
            print "Cannot find the apk you specified: %s" % options.apk
            return False

        if not options.browser in browsermap:
            print "The browser you specified: %s is not recognized, consult \
                    the browsermap at the top of this file" % options.browser
            return False

        if not os.path.exists(options.timecmd):
            print "Cannot find time command at: %s" % options.timecmd
            return False

        if not os.path.exists(options.script):
            print "Cannot find script at: %s" % options.script
            return False

        print "opts: %s" % options
        return options


class StartupTest:
    def __init__(self, options, logcallback=None):
        self.adb = os.path.join(options.sdk, "platform-tools", "adb")
        # In order to use the devicemangerADB the adb command needs to be
        # in the path.  Note that this may cause memory leaks on os x as per
        # the python documentation
        if sys.platform == "darwin" or sys.platform == "linux2":
            os.environ["PATH"] = os.environ["PATH"] + ":" + os.path.join(options.sdk, "platform-tools")
        else:
            os.environ["PATH"] = os.environ["PATH"] + ";" + os.path.join(options.sdk, "platform-tools")
        self.script = options.script
        self.timecmd = options.timecmd
        self.testroot = options.testroot
        self.iterations = options.iterations
        self.apk = options.apk
        self.flashlen = options.flash_length
        self.pauselen = options.pause_length
        self.browser = options.browser
        self.url = options.url
        self.readlen = options.read_length

        # TODO: Probably should be a python logger
        # This is a method that is called: log(msg, isError=False)
        if logcallback:
            self.log = logcallback
        else:
            self.log = self.backuplogger

    def backuplogger(self, msg, isError=False):
        print msg

    def prepare_phone(self):
        self.log("Preparing Phone")
        try:
            # Create our testroot
            self.log(self._run_adb("shell", ["mkdir", self.testroot]))

            # Copy our time script into place
            self.log(self._run_adb("push", [self.timecmd, "/data/local/"]))

            # Chmod our time script - it's overkill but never trust android
            self.log(self._run_adb("shell", ["chmod", "777",
                                             "/data/local/%s" % os.path.basename(self.timecmd)]))

            # Copy our runscript into place
            self.log(self._run_adb("push", [self.script, self.testroot]))

        except Exception as e:
            self.log("Failed to prepare phone due to %s" % e, isError=True)
            return False
        return True

    def run(self):
        # Assume the script has been pushed to the phone, set up the path for adb
        phonescript = self.testroot + "/" + os.path.split(self.script)[1]

        # Instantiate our devicemanger for the kill functionality
        # Note that our appname is everything left of the starting intent
        appname = browsermap[self.browser].split("/")[0]
        dm = devicemanagerADB.DeviceManagerADB(packageName=appname)

        self.log("Running %s for %s iterations" % (self.browser, self.iterations))
        for i in range(self.iterations):
            # Set up our browser command so it's ready when we need it
            browsercmd = ["sh", phonescript, browsermap[self.browser],
                          self.url]
            # First, we flash our "setup" screen as a marker for the video
            # and we hold it for flashlen seconds
            self.log(self._run_adb("shell", ["am", "start", "-a",
                    "android.intent.action.MAIN", "-n", "com.android.settings/.Settings"]))
            sleep(self.flashlen)

            # Run the browser
            self.log(self._run_adb("shell", browsercmd))

            # Reading Delay - let the numbers be displayed long enough on video
            # to be read.
            sleep(self.readlen)

            # Kill the browser - we use the devicemanagerADB for this because it's
            # easier than re-writing all that code
            if not dm.killProcess(appname):
                self.log("ERROR: Could not kill process ending program now")
                sys.exit(1)

            # We will now return to the settings screen (remember our flash
            # from earlier?  So go back to the home screen - the key code
            # for the home button is 3
            self.log(self._run_adb("shell", ["input", "keyevent", "3"]))

            # Pause for pause length now, to let GC's finish
            # TODO: can we cause a system GC ourselves?
            sleep(self.pauselen)

    # cmd must be an array!
    def _run_adb(self, adbcmd, cmd, inshell=False):
        print "run adb cmd: %s" % subprocess.list2cmdline([self.adb, adbcmd] + cmd)
        if (inshell):
            p = subprocess.Popen([self.adb, adbcmd] + cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 shell=True)
        else:
            p = subprocess.Popen([self.adb, adbcmd] + cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        return p.communicate()[0]

def main():
    parser = StartupOptions()
    options, args = parser.parse_args()

    options = parser.verify_options(options)

    if not options:
        print "Failed to validate options, ending test"
        raise Exception('Options', 'Invalid options passed to runstartuptest')

    # Run it
    startuptest = StartupTest(options)
    if startuptest.prepare_phone():
        print "RUNNING!"
        startuptest.run()

if __name__ == '__main__':
    main()

