# Custom firmware code shipped with this config repo (it is itself a Zephyr
# module - see zephyr/module.yml - so ZMK picks this up for every build).
target_sources_ifdef(CONFIG_FORAGER_BATTERY_RESEND app PRIVATE src/battery_resend.c)
