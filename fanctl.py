#!/usr/bin/python3
"""Fan control for the ASUS VivoBook X412DA: run with no arguments for the window."""
import glob
import os
import signal
import subprocess
import sys

# Values for pwm1_enable.
# shortcut: no speed below Auto, because this EC overrides ST98 and ST84 within seconds (tested);
# add a slider if a BIOS or kernel update exposes pwm1.
MODES = {"auto": "2", "full": "0"}


def read(path):
    with open(path) as f:
        return f.read().strip()


def hwmon(name):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(d + "/name") == name:
            return d
    sys.exit(f"No {name} sensor found: this app is made for the ASUS X412DA.")


def apply(mode, enable):
    with open(enable, "w") as f:
        f.write(MODES[mode])


def serve(lines, enable):
    """Apply each valid mode line; always hand the fan back to Auto when the input ends."""
    try:
        for line in lines:
            if line.strip() in MODES:
                apply(line.strip(), enable)
    finally:
        apply("auto", enable)


def helper():
    # SystemExit lets serve() restore Auto on logout or kill too.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(0))
    serve(sys.stdin, hwmon("asus") + "/pwm1_enable")


def gui():
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    GLib.set_prgname("vivobook-fan-control")
    try:
        fan_dir, cpu_dir = hwmon("asus"), hwmon("k10temp")
    except SystemExit as e:
        # Launched from the menu there is no terminal to show the exit message.
        Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                          text=str(e)).run()
        raise

    # Password once here, so every later mode change applies immediately.
    # realpath because the polkit policy matches the installed file, not the /usr/bin symlink.
    proc = subprocess.Popen(
        ["pkexec", os.path.realpath(__file__), "--helper"],
        stdin=subprocess.PIPE, text=True, bufsize=1,
    )

    win = Gtk.Window(title="Fan Control", border_width=16)
    win.set_icon_name("vivobook-fan-control")
    win.connect("destroy", Gtk.main_quit)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    win.add(box)

    status = Gtk.Label(xalign=0)
    box.add(status)

    choices = [
        ("auto", "Auto: the laptop decides, and the lowest setting available"),
        ("full", "Full: maximum fan within seconds"),
    ]
    group, radios = None, []
    for mode, text in choices:
        radio = Gtk.RadioButton.new_with_label_from_widget(group, text)
        group = group or radio
        radio.connect("toggled", lambda r, m=mode: r.get_active() and send(m))
        box.add(radio)
        radios.append(radio)

    note = Gtk.Label(label="After Full, the fan takes about 90 seconds to slow down.", xalign=0)
    box.add(note)

    def disable(message):
        note.set_text(message)
        for radio in radios:
            radio.set_sensitive(False)

    def send(mode):
        try:
            proc.stdin.write(mode + "\n")
        except BrokenPipeError:
            disable("Controls stopped. Close and reopen the app to change modes.")

    def tick():
        temp = int(read(cpu_dir + "/temp1_input")) // 1000
        status.set_text(f"CPU {temp} °C    Fan {read(fan_dir + '/fan1_input')} RPM")
        if proc.poll() is not None:
            disable("Controls are off: the password wasn't accepted or the helper stopped. "
                    "Reopen the app to try again.")
            return False
        return True

    tick()
    GLib.timeout_add_seconds(1, tick)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    helper() if sys.argv[1:] == ["--helper"] else gui()
