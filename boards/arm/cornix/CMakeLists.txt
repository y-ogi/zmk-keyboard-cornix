zephyr_library()
zephyr_library_sources(pinmux.c)
zephyr_library_include_directories(${ZEPHYR_BASE}/drivers)

# Workaround: battery_voltage_divider.c in the ZMK cormoran fork uses
# SAADC_CH_PSELP_PSELP_AnalogInput0 from nrfx MDK headers but does not
# include the nrfx header chain. Define it globally to match nrf52840_bitfields.h.
zephyr_compile_definitions(SAADC_CH_PSELP_PSELP_AnalogInput0=1)