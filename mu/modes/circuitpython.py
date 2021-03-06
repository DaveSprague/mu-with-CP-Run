"""
A mode for working with Circuit Python boards.

Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import time
import ctypes
from shutil import copyfile
from subprocess import check_output
from mu.modes.base import MicroPythonMode
from mu.modes.api import ADAFRUIT_APIS, SHARED_APIS
from mu.interface.panes import CHARTS
from mu.logic import get_pathname


class CircuitPythonMode(MicroPythonMode):
    """
    Represents the functionality required by the CircuitPython mode.
    """

    name = _("CircuitPython")
    description = _("Write code for boards running CircuitPython.")
    icon = "circuitpython"
    save_timeout = 0  #: No auto-save on CP boards. Will restart.
    connected = True  #: is the board connected.
    force_interrupt = False  #: NO keyboard interrupt on serial connection.
    valid_boards = [
        (0x2B04, 0xC00C),  # Particle Argon
        (0x2B04, 0xC00D),  # Particle Boron
        (0x2B04, 0xC00E),  # Particle Xenon
        (0x239A, None),  # Any Adafruit Boards
        # Non-Adafruit boards
        (0x1209, 0xBAB1),  # Electronic Cats Meow Meow
        (0x1209, 0xBAB2),  # Electronic Cats CatWAN USBStick
        (0x1209, 0xBAB3),  # Electronic Cats Bast Pro Mini M0
        (0x1B4F, 0x8D22),  # SparkFun SAMD21 Mini Breakout
        (0x1B4F, 0x8D23),  # SparkFun SAMD21 Dev Breakout
        (0x1209, 0x2017),  # Mini SAM M4
        (0x1209, 0x7102),  # Mini SAM M0
    ]
    # Modules built into CircuitPython which mustn't be used as file names
    # for source code.
    module_names = {
        "storage",
        "os",
        "touchio",
        "microcontroller",
        "bitbangio",
        "digitalio",
        "audiobusio",
        "multiterminal",
        "nvm",
        "pulseio",
        "usb_hid",
        "analogio",
        "time",
        "busio",
        "random",
        "audioio",
        "sys",
        "math",
        "builtins",
    }

    def actions(self):
        """
        Return an ordered list of actions provided by this module. An action
        is a name (also used to identify the icon) , description, and handler.
        """
        buttons = [
            {
                "name": "serial",
                "display_name": _("Serial"),
                "description": _("Open a serial connection to your device."),
                "handler": self.toggle_repl,
                "shortcut": "CTRL+Shift+U",
            }
        ]
        if self.editor.circuitpython_run:
            buttons.insert(
                0,
                {
                    "name": "run",
                    "display_name": _("Run"),
                    "description": _(
                        "Save and run your current file " "on CIRCUITPY"
                    ),
                    "handler": self.run,
                    "shortcut": "CTRL+Shift+R",
                },
            )
        if CHARTS:
            buttons.append(
                {
                    "name": "plotter",
                    "display_name": _("Plotter"),
                    "description": _("Plot incoming REPL data."),
                    "handler": self.toggle_plotter,
                    "shortcut": "CTRL+Shift+P",
                }
            )
        return buttons

    def workspace_dir(self):
        """
        Return the default location on the filesystem for opening and closing
        files.
        """
        device_dir = None
        # Attempts to find the path on the filesystem that represents the
        # plugged in CIRCUITPY board.
        if os.name == "posix":
            # We're on Linux or OSX
            for mount_command in ["mount", "/sbin/mount"]:
                try:
                    mount_output = check_output(mount_command).splitlines()
                    mounted_volumes = [x.split()[2] for x in mount_output]
                    for volume in mounted_volumes:
                        if volume.endswith(b"CIRCUITPY"):
                            device_dir = volume.decode("utf-8")
                except FileNotFoundError:
                    next
        elif os.name == "nt":
            # We're on Windows.

            def get_volume_name(disk_name):
                """
                Each disk or external device connected to windows has an
                attribute called "volume name". This function returns the
                volume name for the given disk/device.

                Code from http://stackoverflow.com/a/12056414
                """
                vol_name_buf = ctypes.create_unicode_buffer(1024)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(disk_name),
                    vol_name_buf,
                    ctypes.sizeof(vol_name_buf),
                    None,
                    None,
                    None,
                    None,
                    0,
                )
                return vol_name_buf.value

            #
            # In certain circumstances, volumes are allocated to USB
            # storage devices which cause a Windows popup to raise if their
            # volume contains no media. Wrapping the check in SetErrorMode
            # with SEM_FAILCRITICALERRORS (1) prevents this popup.
            #
            old_mode = ctypes.windll.kernel32.SetErrorMode(1)
            try:
                for disk in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    path = "{}:\\".format(disk)
                    if (
                        os.path.exists(path)
                        and get_volume_name(path) == "CIRCUITPY"
                    ):
                        return path
            finally:
                ctypes.windll.kernel32.SetErrorMode(old_mode)
        else:
            # No support for unknown operating systems.
            raise NotImplementedError('OS "{}" not supported.'.format(os.name))

        if device_dir:
            # Found it!
            self.connected = True
            return device_dir
        else:
            # Not plugged in? Just return Mu's regular workspace directory
            # after warning the user.
            wd = super().workspace_dir()
            if self.connected:
                m = _("Could not find an attached CircuitPython device.")
                info = _(
                    "Python files for CircuitPython devices"
                    " are stored on the device. Therefore, to edit"
                    " these files you need to have the device plugged in."
                    " Until you plug in a device, Mu will use the"
                    " directory found here:\n\n"
                    " {}\n\n...to store your code."
                )
                self.view.show_message(m, info.format(wd))
                self.connected = False
            return wd

    def workspace_dir_cp(self):
        """
        Is the file currently being edited located on CIRCUITPY.
        """
        return "CIRCUITPY" in str(get_pathname(self))

    def workspace_cp_avail(self):
        """
        Is CIRCUITPY available.
        """
        return "CIRCUITPY" in str(self.workspace_dir())

    def run_circuitpython_lib_copy(self, pathname, dst_dir):
        """
        Optionally copy lib files to CIRCUITPY.
        """
        lib_dir = os.path.dirname(pathname) + "/lib"
        if not os.path.isdir(lib_dir):
            return
        replace_cnt = 0
        for root, dirs, files in os.walk(lib_dir):
            for filename in files:
                src_lib = lib_dir + "/" + filename
                dst_lib_dir = dst_dir + "/lib"
                dst_lib = dst_lib_dir + "/" + filename
                if not os.path.exists(dst_lib):
                    replace_lib = True
                else:
                    src_tm = time.ctime(os.path.getmtime(src_lib))
                    dst_tm = time.ctime(os.path.getmtime(dst_lib))
                    replace_lib = src_tm > dst_tm
                if replace_lib:
                    if replace_cnt == 0:
                        if not os.path.exists(dst_lib_dir):
                            os.makedirs(dst_lib_dir)
                    copyfile(src_lib, dst_lib)
                    replace_cnt = replace_cnt + 1
        # let libraries load before copying source main source file
        if replace_cnt > 0:
            time.sleep(4)

    def run(self, event):
        """
        Save the file and copy to CIRCUITPY if not already there and available.
        """
        self.editor.save()

        if not self.workspace_dir_cp() and self.workspace_cp_avail():
            pathname = get_pathname(self)
            if pathname:
                dst_dir = self.workspace_dir()
                if pathname.find("/lib/") == -1:
                    dst = dst_dir + "/code.py"
                else:
                    dst = dst_dir + "/lib/" + os.path.basename(pathname)

                # copy library files on to device if not working on the device
                if self.editor.circuitpython_lib:
                    self.run_circuitpython_lib_copy(pathname, dst_dir)

                # copy edited source file on to device
                copyfile(pathname, dst)

    def api(self):
        """
        Return a list of API specifications to be used by auto-suggest and call
        tips.
        """
        return SHARED_APIS + ADAFRUIT_APIS
