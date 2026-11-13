"""
Matplotlib dashboard for the HVAC HMI. Draws what the HMI polled and queues
operator writes; it never talks BACnet itself.
"""

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button, TextBox


def start_plot(data_buf, state, lock, cmd_q, use_fahrenheit=False, title=None):
    unit = "°F" if use_fahrenheit else "°C"
    setp_min = 60.0 if use_fahrenheit else 15.0
    setp_max = 95.0 if use_fahrenheit else 35.0
    temp_pad = 4.0 if use_fahrenheit else 2.0

    def to_display(c):
        return c * 9.0 / 5.0 + 32.0 if use_fahrenheit else c

    def from_display(d):
        return (d - 32.0) * 5.0 / 9.0 if use_fahrenheit else d
    TEMP_COLOR = "#007ACC"
    SETPOINT_COLOR = "#FF8C00"
    CHILLER_COLOR = "#004B6B"
    INTAKE_COLOR = "#228B22"
    EXHAUST_COLOR = "#9B1C31"

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "legend.fontsize": 9,
            "axes.facecolor": "#f5f5f5",
            "figure.facecolor": "#f5f5f5",
            "grid.color": "#d0d0d0",
            "axes.edgecolor": "#666666",
        }
    )

    fig = plt.figure(num=title, figsize=(11, 6))

    gs = fig.add_gridspec(
        4,
        4,
        height_ratios=[3.5, 1.0, 1.0, 1.5],
        width_ratios=[1.0, 1.0, 1.0, 1.0],
        wspace=0.6,
        hspace=0.7,
    )

    ax_temp = fig.add_subplot(gs[0, 0:3])
    ax_chill = fig.add_subplot(gs[0, 3])
    ax_intake = fig.add_subplot(gs[1, 3])
    ax_exhaust = fig.add_subplot(gs[2, 3])
    ax_controls = fig.add_subplot(gs[1:4, 0:3])
    ax_controls.axis("off")

    (line_temp,) = ax_temp.plot(
        [], [], lw=2, label=f"Current Temp ({unit})", color=TEMP_COLOR
    )
    (line_setp,) = ax_temp.plot(
        [], [], lw=2, linestyle="--", label=f"Setpoint ({unit})", color=SETPOINT_COLOR
    )

    ax_temp.set_title("Server Room Temperature")
    ax_temp.set_xlabel("Time (s)")
    ax_temp.set_ylabel(f"Temperature ({unit})")
    ax_temp.legend(loc="upper right", frameon=True)

    for ax in (ax_temp, ax_chill, ax_intake, ax_exhaust):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    (line_chill,) = ax_chill.plot([], [], lw=2, color=CHILLER_COLOR)
    ax_chill.set_ylabel("Chiller (%)")
    ax_chill.set_ylim(0, 100)
    ax_chill.set_title("Chiller", pad=6)

    (line_intake,) = ax_intake.plot([], [], lw=2, color=INTAKE_COLOR)
    ax_intake.set_ylabel("Intake (%)")
    ax_intake.set_ylim(0, 100)
    ax_intake.set_xlabel("Time (s)")

    (line_exhaust,) = ax_exhaust.plot([], [], lw=2, color=EXHAUST_COLOR)
    ax_exhaust.set_ylabel("Exhaust (%)")
    ax_exhaust.set_ylim(0, 100)
    ax_exhaust.set_xlabel("Time (s)")

    ctrl_pos = ax_controls.get_position()
    left = ctrl_pos.x0
    width = ctrl_pos.width
    bottom = ctrl_pos.y0
    height = ctrl_pos.height
    slider_h = height / 6.0

    fig.text(
        left + 0.01 * width,
        bottom + height - slider_h * 0.3,
        "Controls",
        fontsize=12,
        fontweight="bold",
    )

    ax_s_setp = fig.add_axes(
        [left + 0.02 * width, bottom + 4 * slider_h, width * 0.57, slider_h * 0.6]
    )
    ax_s_intake = fig.add_axes(
        [left + 0.02 * width, bottom + 3 * slider_h, width * 0.57, slider_h * 0.6]
    )
    ax_s_exhaust = fig.add_axes(
        [left + 0.02 * width, bottom + 2 * slider_h, width * 0.57, slider_h * 0.6]
    )

    tb_x = left + 0.02 * width + width * 0.59
    tb_w = width * 0.10
    tb_h = slider_h * 0.6
    ax_tb_setp   = fig.add_axes([tb_x, bottom + 4 * slider_h, tb_w, tb_h])
    ax_tb_intake  = fig.add_axes([tb_x, bottom + 3 * slider_h, tb_w, tb_h])
    ax_tb_exhaust = fig.add_axes([tb_x, bottom + 2 * slider_h, tb_w, tb_h])

    btn_width = width * 0.2
    btn_height = slider_h * 2.1
    btn_left = left + 0.81 * width
    btn_bottom = bottom + 2.3 * slider_h
    ax_btn_estop = fig.add_axes([btn_left, btn_bottom, btn_width, btn_height])

    with lock:
        init_setp = state.setpoint_c
        init_intake = state.intake_pct
        init_exhaust = state.exhaust_pct
    initial_setp_disp = to_display(init_setp)

    s_setp = Slider(
        ax=ax_s_setp,
        label=f"Setpoint ({unit})",
        valmin=setp_min,
        valmax=setp_max,
        valinit=initial_setp_disp,
        facecolor=TEMP_COLOR,
    )
    s_intake = Slider(
        ax=ax_s_intake,
        label="Intake Fan (%)",
        valmin=0.0,
        valmax=100.0,
        valinit=init_intake,
        facecolor=INTAKE_COLOR,
    )
    s_exhaust = Slider(
        ax=ax_s_exhaust,
        label="Exhaust Fan (%)",
        valmin=0.0,
        valmax=100.0,
        valinit=init_exhaust,
        facecolor=EXHAUST_COLOR,
    )

    for s in (s_setp, s_intake, s_exhaust):
        if s.valtext is not None:
            s.valtext.set_visible(False)

    tb_setp    = TextBox(ax_tb_setp,   "", initial=f"{initial_setp_disp:.1f}")
    tb_intake  = TextBox(ax_tb_intake,  "", initial=f"{init_intake:.0f}")
    tb_exhaust = TextBox(ax_tb_exhaust, "", initial=f"{init_exhaust:.0f}")

    btn_estop = Button(ax_btn_estop, "E-STOP: OFF")
    btn_estop.label.set_fontweight("bold")

    def on_setp_change(val):
        cmd_q.put(("setpoint", from_display(val)))
        tb_setp.set_val(f"{val:.1f}")

    def on_intake_change(val_pct):
        cmd_q.put(("intake", float(val_pct)))
        tb_intake.set_val(f"{val_pct:.0f}")

    def on_exhaust_change(val_pct):
        cmd_q.put(("exhaust", float(val_pct)))
        tb_exhaust.set_val(f"{val_pct:.0f}")

    def on_setp_submit(text):
        try:
            val = float(text)
            val = max(setp_min, min(setp_max, val))
            s_setp.set_val(val)
        except ValueError:
            pass

    def on_intake_submit(text):
        try:
            val = float(text)
            val = max(0.0, min(100.0, val))
            s_intake.set_val(val)
        except ValueError:
            pass

    def on_exhaust_submit(text):
        try:
            val = float(text)
            val = max(0.0, min(100.0, val))
            s_exhaust.set_val(val)
        except ValueError:
            pass

    s_setp.on_changed(on_setp_change)
    s_intake.on_changed(on_intake_change)
    s_exhaust.on_changed(on_exhaust_change)

    tb_setp.on_submit(on_setp_submit)
    tb_intake.on_submit(on_intake_submit)
    tb_exhaust.on_submit(on_exhaust_submit)

    def update_estop_button():
        with lock:
            estop_on = state.estop
        if estop_on:
            btn_estop.label.set_text("E-STOP: ON")
            btn_estop.label.set_color("white")
            btn_estop.color = "#b22222"
            btn_estop.hovercolor = "#b22222"
        else:
            btn_estop.label.set_text("E-STOP: OFF")
            btn_estop.label.set_color("black")
            btn_estop.color = "#d3d3d3"
            btn_estop.hovercolor = "#e0e0e0"

        btn_estop.ax.set_facecolor(btn_estop.color)
        fig.canvas.draw_idle()

    def on_estop_clicked(_event):
        with lock:
            estop_on = state.estop
        cmd_q.put(("estop", not estop_on))

    btn_estop.on_clicked(on_estop_clicked)
    update_estop_button()

    def animate(_):
        update_estop_button()

        with lock:
            times = list(data_buf["time"])
            temps = list(data_buf["temp"])
            setps = list(data_buf["setp"])
            chills = list(data_buf["chill"])
            intakes = list(data_buf["intake"])
            exhausts = list(data_buf["exhaust"])

        if not times:
            return line_temp, line_setp, line_chill, line_intake, line_exhaust

        t0 = times[0]
        x = [t - t0 for t in times]

        temp_vals = [to_display(c) for c in temps]
        setp_vals = [to_display(c) for c in setps]

        line_temp.set_data(x, temp_vals)
        line_setp.set_data(x, setp_vals)
        line_chill.set_data(x, chills)
        line_intake.set_data(x, intakes)
        line_exhaust.set_data(x, exhausts)

        xmax = x[-1]
        xmin = max(0.0, xmax - 120.0)
        for ax in (ax_temp, ax_chill, ax_intake, ax_exhaust):
            ax.set_xlim(xmin, xmax + 1.0)

        tmin = min(temp_vals)
        tmax = max(temp_vals)
        ax_temp.set_ylim(tmin - temp_pad, tmax + temp_pad)

        return line_temp, line_setp, line_chill, line_intake, line_exhaust

    anim = FuncAnimation(fig, animate, interval=1000, cache_frame_data=False)
    fig._anim = anim

    plt.show()


def _webagg_fill_window(title):
    # Size the WebAgg figure to the browser window instead of a fixed canvas
    # that scrolls. mpl.js already re-renders the figure when its canvas
    # container resizes, so we just size that container to the window.
    import io
    import json
    from matplotlib.backends import backend_webagg_core as wac

    js = """
(function(){
  document.title=TITLE;
  function fit(){
    var c=document.querySelector('.mpl-canvas');if(!c)return false;
    var cd=c.parentElement;
    var de=document.documentElement;de.style.height='100%';de.style.overflow='hidden';
    var b=document.body.style;b.margin='0';b.height='100%';b.overflow='hidden';
    var figs=document.getElementById('figures');if(figs)figs.style.margin='0';
    var root=document.getElementById('figure-div');if(root){root.style.display='block';root.style.width='100%';}
    if(cd.parentElement){cd.parentElement.style.display='block';cd.parentElement.style.width='100%';}
    cd.style.width=Math.max(200,window.innerWidth-2)+'px';
    cd.style.height=Math.max(150,window.innerHeight-84)+'px';
    return true;
  }
  window.addEventListener('resize',fit);
  var done=0,n=0,iv=setInterval(function(){
    var c=document.querySelector('.mpl-canvas');n++;
    if(c&&c.width>0){fit();if(++done>=3)clearInterval(iv);}
    if(n>200)clearInterval(iv);
  },150);
})();
""".replace("TITLE", json.dumps(title))
    orig = wac.FigureManagerWebAgg.get_javascript.__func__

    def patched(cls, stream=None):
        buf = io.StringIO()
        orig(cls, buf)
        out = buf.getvalue() + js
        if stream is None:
            return out
        stream.write(out)

    wac.FigureManagerWebAgg.get_javascript = classmethod(patched)
