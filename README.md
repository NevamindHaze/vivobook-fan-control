# VivoBook Fan Control

A small window for the ASUS VivoBook X412DA on Linux Mint. It switches the fan between **Auto** and **Full** right away, and the fan returns to Auto when the app closes.

It also shows live graphs of the last 5 minutes of CPU temperature, fan speed, CPU load and CPU clock, updated every second, plus current GPU and SSD temperatures. Hover over a graph to read an earlier value. Graphs start empty each time the app opens, and they keep running if you cancel the password prompt.

## Install

```bash
sudo install -d /etc/apt/keyrings
```

```bash
curl -fsSL https://nevamindhaze.github.io/vivobook-fan-control/key.gpg | sudo tee /etc/apt/keyrings/vivobook-fan-control.gpg > /dev/null
```

```bash
echo "deb [signed-by=/etc/apt/keyrings/vivobook-fan-control.gpg] https://nevamindhaze.github.io/vivobook-fan-control stable main" | sudo tee /etc/apt/sources.list.d/vivobook-fan-control.list
```

```bash
sudo apt update
```

```bash
sudo apt install vivobook-fan-control
```

Then open **Fan Control** from the menu. It asks for your password once when it starts.

## Limits

- **No speed below Auto.** On the X412DA the `asus` driver offers only Auto and Full, and the embedded controller overrode the firmware calls `ST98` and `ST84` in testing.
- **After Full, the fan slows down gradually.** It took about 90 seconds in testing, and the firmware controls this.
- **Only tested on one laptop.** That's an X412DA with a Ryzen 5 3500U on Linux Mint 22.3. It needs the `asus` and `k10temp` sensors and shows an error without them. Other ASUS laptops may work, but that's untested.

Running on Full for long periods adds fan wear and noise.

## Develop

```bash
python3 test_fanctl.py
```

`./build.sh` runs the test, builds the package, and regenerates the signed apt repository in `docs/`. It needs the signing key in your GPG keyring.

## License

[MIT](LICENSE)
