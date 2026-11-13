/*
 * Re-send this half's battery level to the split central (the dongle).
 *
 * ZMK raises zmk_battery_state_changed - and therefore sends the level over
 * the split transport - only when the level changes. With BLE the central
 * reads the level itself on connect; ESB has no connection, so a dongle that
 * boots after the halves would never learn it.
 *
 * So the level is sent again once typing on this half pauses for
 * CONFIG_FORAGER_BATTERY_RESEND_QUIET_MS, at most once every
 * CONFIG_FORAGER_BATTERY_RESEND_MIN_GAP_S seconds. Waiting for a pause keeps
 * this packet out of the way of key events. It goes directly over the split
 * transport (not by re-raising the battery event, so local listeners such as
 * the RGB LED widget are not re-triggered).
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <zmk/battery.h>
#include <zmk/event_manager.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/split/peripheral.h>
#include <zmk/split/transport/types.h>

LOG_MODULE_REGISTER(forager_battery_resend, CONFIG_ZMK_LOG_LEVEL);

#define QUIET K_MSEC(CONFIG_FORAGER_BATTERY_RESEND_QUIET_MS)
#define MIN_GAP_MS (CONFIG_FORAGER_BATTERY_RESEND_MIN_GAP_S * 1000LL)

static int64_t last_sent_ms;
static bool sent_once;

static bool resend_due(void) { return !sent_once || k_uptime_get() - last_sent_ms >= MIN_GAP_MS; }

static void resend_work_cb(struct k_work *work) {
    uint8_t level = zmk_battery_state_of_charge();

    /* 0 = not sampled yet; ZMK's own change event will carry the first value */
    if (level == 0) {
        return;
    }

    struct zmk_split_transport_peripheral_event ev = {
        .type = ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_BATTERY_EVENT,
        .data = {.battery_event = {.level = level}},
    };
    int rc = zmk_split_peripheral_report_event(&ev);
    if (rc < 0) {
        LOG_WRN("Failed to re-send battery level %d (%d)", level, rc);
        return;
    }

    last_sent_ms = k_uptime_get();
    sent_once = true;
}

static K_WORK_DELAYABLE_DEFINE(resend_work, resend_work_cb);

static int battery_resend_listener(const zmk_event_t *eh) {
    if (as_zmk_position_state_changed(eh) != NULL && resend_due()) {
        /* Every key event (press or release) pushes the send further out */
        k_work_reschedule(&resend_work, QUIET);
    }

    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(forager_battery_resend, battery_resend_listener);
ZMK_SUBSCRIPTION(forager_battery_resend, zmk_position_state_changed);
