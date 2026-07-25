# Forager ZMK Module

This is the ZMK module for [the Forager keyboard](https://github.com/carrefinho/forager).

[ZMK Studio](https://zmk.dev/docs/features/studio) is supported and enabled by default.

Featuring the awesome [zmk-rgbled-widget by caksoylar](https://github.com/caksoylar/zmk-rgbled-widget).

> [!IMPORTANT]
>
> This module has been upgraded to work with the Zephyr 4.1 version of ZMK. If you're upgrading from an earlier version (v0.3 or earlier), you'll need to update your `build.yaml` to use new board name:
>
> ```diff
>  ---
>  include:
>-   - board: seeeduino_xiao_ble
>+   - board: xiao_ble//zmk
> ```
>
> If you'd like to stick with ZMK v0.3, you can use the [zmk-v0.3 branch](https://github.com/carrefinho/forager-zmk-module/tree/zmk-v0.3).

# Usage

Add these lines to `config/west.yml` in your `zmk-config` repository:

```yaml
manifest:
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
    - name: carrefinho                            # <---
      url-base: https://github.com/carrefinho     # <---
    - name: caksoylar                             # <---
      url-base: https://github.com/caksoylar      # <---
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
    - name: forager-zmk-module                    # <---
      remote: carrefinho                          # <---
      revision: main                              # <---
    - name: zmk-rgbled-widget                     # <---
      remote: caksoylar                           # <---
      revision: main                              # <---
  self:
    path: config
```

Then add `forager_left` and `forager_right` shields to your `build.yaml`:

```yaml
---
include:
  - board: xiao_ble//zmk
    shield: forager_left rgbled_adapter
    snippet: studio-rpc-usb-uart
  - board: xiao_ble//zmk
    shield: forager_right rgbled_adapter
```

This module also supports [ZMK dongle mode](https://zmk.dev/docs/development/hardware-integration/dongle). See [`build.yaml`](build.yaml#L10) for dongle build configuration.

For more information on ZMK Modules and building locally, see [the ZMK docs page on modules.](https://zmk.dev/docs/features/modules)

To customize behavior of the RGB LED, see [rgbled-widget documentation.](https://github.com/caksoylar/zmk-rgbled-widget)