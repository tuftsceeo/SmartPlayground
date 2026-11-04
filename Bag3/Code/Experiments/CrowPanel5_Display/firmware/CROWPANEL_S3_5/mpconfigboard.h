#ifndef MICROPY_HW_BOARD_NAME
// Can be set by mpconfigboard.cmake.
#define MICROPY_HW_BOARD_NAME               "Generic ESP32S3 module"
#endif
#define MICROPY_HW_MCU_NAME                 "ESP32S3"

// Enable UART REPL for modules that have an external USB-UART and don't use native USB.
#define MICROPY_HW_ENABLE_UART_REPL         (1)

#define MICROPY_HW_I2C0_SCL                 (9)
#define MICROPY_HW_I2C0_SDA                 (8)

// GPIO19/20 carry touch I2C; the REPL is on UART0 via the CH340.
#undef MICROPY_HW_USB_CDC
#define MICROPY_HW_USB_CDC                  (0)
#undef MICROPY_HW_ENABLE_USBDEV
#define MICROPY_HW_ENABLE_USBDEV            (0)
#undef MICROPY_HW_ESP_USB_SERIAL_JTAG
#define MICROPY_HW_ESP_USB_SERIAL_JTAG      (0)
