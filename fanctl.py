#!/usr/bin/python3
"""Fan control for the ASUS VivoBook X412DA: run with no arguments for the window."""
import collections
import glob
import math
import os
import re
import signal
import subprocess
import sys

# Values for pwm1_enable.
# shortcut: no speed below Auto, because this EC overrides ST98 and ST84 within seconds (tested);
# add a slider if a BIOS or kernel update exposes pwm1.
MODES = {"auto": "2", "full": "0"}

HISTORY = 300  # seconds shown on each graph, at one sample per second
LINE_LIGHT, LINE_DARK = (0, 0x89, 0x7b), (0x1f, 0xa9, 0x9c)


def read(path):
    with open(path) as f:
        return f.read().strip()


def find_hwmon(name):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(d + "/name") == name:
            return d
    return None


def hwmon(name):
    return find_hwmon(name) or sys.exit(f"No {name} sensor found: this app is made for the ASUS X412DA.")


def cpu_times(stat):
    """(total, idle) jiffies from the first line of /proc/stat; iowait counts as idle."""
    fields = [int(x) for x in stat.splitlines()[0].split()[1:]]
    return sum(fields), fields[3] + fields[4]


def cpu_percent(prev, cur):
    total = cur[0] - prev[0]
    return 100 * (1 - (cur[1] - prev[1]) / total) if total > 0 else 0.0


def average_mhz(cpuinfo):
    values = [float(x) for x in re.findall(r"cpu MHz\s*:\s*([\d.]+)", cpuinfo)]
    return sum(values) / len(values) if values else 0.0


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

    def add_chart(title, unit, bottom, top, column, row):
        """One graph per measure, so each keeps its own single axis."""
        samples = collections.deque(maxlen=HISTORY)
        chart = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, vexpand=True)
        header = Gtk.Label(xalign=0)
        area = Gtk.DrawingArea(hexpand=True, vexpand=True, has_tooltip=True)
        area.set_size_request(300, 110)
        area.get_accessible().set_name(title + " graph")
        chart.add(header)
        chart.add(area)
        grid.attach(chart, column, row, 1, 1)

        def scale_top():
            return max(top, max(samples, default=top))

        def plot_x(width, age):
            return 44 + (width - 52) * (1 - age / (HISTORY - 1))

        def draw(widget, cr):
            width, height = widget.get_allocated_width(), widget.get_allocated_height()
            ink = widget.get_style_context().get_color(widget.get_state_flags())
            dark = ink.red + ink.green + ink.blue > 1.5
            plot_top, plot_bottom = 6, height - 20
            ceiling = scale_top()

            def plot_y(value):
                share = (min(value, ceiling) - bottom) / (ceiling - bottom)
                return plot_bottom - max(share, 0) * (plot_bottom - plot_top)

            cr.set_font_size(11)
            for value in (bottom, (bottom + ceiling) / 2, ceiling):
                y = plot_y(value)
                cr.set_source_rgba(ink.red, ink.green, ink.blue, 0.15)
                cr.set_line_width(1)
                cr.move_to(44, y)
                cr.line_to(width - 8, y)
                cr.stroke()
                cr.set_source_rgba(ink.red, ink.green, ink.blue, 0.7)
                label = f"{value:.0f}"
                cr.move_to(38 - cr.text_extents(label).width, y + 4)
                cr.show_text(label)
            cr.move_to(44, height - 4)
            cr.show_text("5 min ago")
            cr.move_to(width - 8 - cr.text_extents("now").width, height - 4)
            cr.show_text("now")

            if samples:
                r, g, b = LINE_DARK if dark else LINE_LIGHT
                cr.set_source_rgb(r / 255, g / 255, b / 255)
                cr.set_line_width(2)
                cr.set_line_join(1)  # round
                newest = len(samples) - 1
                points = [(plot_x(width, newest - i), plot_y(v)) for i, v in enumerate(samples)]
                cr.move_to(*points[0])
                for point in points[1:]:
                    cr.line_to(*point)
                cr.stroke()
                cr.arc(*points[-1], 4, 0, 2 * math.pi)
                cr.fill()

        def tooltip(widget, x, y, keyboard, tip):
            if not samples:
                return False
            width = widget.get_allocated_width()
            age = round((1 - (x - 44) / (width - 52)) * (HISTORY - 1))
            if not 0 <= age < len(samples):
                return False
            tip.set_text(f"{samples[len(samples) - 1 - age]:.0f} {unit}, {age} s ago")
            return True

        area.connect("draw", draw)
        area.connect("query-tooltip", tooltip)

        def add(value):
            samples.append(value)
            header.set_text(f"{title}: {value:.0f} {unit}    low {min(samples):.0f}    high {max(samples):.0f}")
            area.queue_draw()

        return add

    grid = Gtk.Grid(column_spacing=16, row_spacing=12, column_homogeneous=True, row_homogeneous=True)
    box.pack_start(grid, True, True, 0)
    add_temp = add_chart("CPU temperature", "°C", 30, 100, 0, 0)
    add_rpm = add_chart("Fan speed", "RPM", 0, 7000, 1, 0)
    add_load = add_chart("CPU load", "%", 0, 100, 0, 1)
    add_mhz = add_chart("CPU clock", "MHz", 0, 4000, 1, 1)

    others = [(label, d) for label, d in (("GPU", find_hwmon("amdgpu")), ("SSD", find_hwmon("nvme"))) if d]
    other_temps = Gtk.Label(xalign=0)
    box.add(other_temps)

    previous = [cpu_times(read("/proc/stat"))]
    controls_on = [True]

    def tick():
        add_temp(int(read(cpu_dir + "/temp1_input")) / 1000)
        add_rpm(int(read(fan_dir + "/fan1_input")))
        current = cpu_times(read("/proc/stat"))
        if current[0] > previous[0][0]:  # the first tick has no elapsed time to measure
            add_load(cpu_percent(previous[0], current))
        previous[0] = current
        add_mhz(average_mhz(read("/proc/cpuinfo")))

        parts = []
        for label, d in others:
            try:  # a sleeping GPU or SSD can refuse the read
                parts.append(f"{label} {int(read(d + '/temp1_input')) // 1000} °C")
            except OSError:
                parts.append(f"{label} unavailable")
        other_temps.set_text("    ".join(parts))

        if controls_on[0] and proc.poll() is not None:
            controls_on[0] = False
            disable("Fan controls are off: the password wasn't accepted or the helper stopped. "
                    "Graphs keep running. Reopen the app to try again.")
        return True

    tick()
    GLib.timeout_add_seconds(1, tick)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    helper() if sys.argv[1:] == ["--helper"] else gui()
