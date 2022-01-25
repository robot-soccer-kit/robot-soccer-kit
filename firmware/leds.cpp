//#define DEBUG
#include <stdio.h>
#include "leds.h"
#include "hardware.h"
#include <wirish/HardwareSPI.h>
#include <dma.h>
#include <terminal.h>
#include <dxl.h>
#include <function.h>

HardwareSPI spi(LEDS_SPI);

// Having references to the GPIO device and bit provide a faster further
// access to this pin
// static gpio_dev *dev = PIN_MAP[PIN_LEDS].gpio_device;
// static uint8 bit = PIN_MAP[PIN_LEDS].gpio_bit;

Function breath;
float breathPhase = 0;
float breathPhase2 = 0;
float breathPhase3 = 0;

// Blink parameters
int blink_duration = 200;//[ms]
bool blink_increasing = true;
float blink_start_time = 0;
struct leds leds_max;

// Bad leds
int bad_leds_blink_duration = 400;
uint8_t mode = LEDS_CUSTOM;
uint8_t led1_r, led1_g, led1_b;
uint8_t led1b_r, led1b_g, led1b_b;
uint8_t led2_r, led2_g, led2_b;
uint8_t led2b_r, led2b_g, led2b_b;
uint8_t led3_r, led3_g, led3_b;
uint8_t led3b_r, led3b_g, led3b_b;

static dma_tube_config tube_config;
static uint8_t data[250];
static int data_pos = 0;
static int data_bit = 0;
static bool dma_transmitting = false;

static void reset_bits()
{
    for (int k=0; k<sizeof(data); k++) {
        data[k] = 0;
    }
    data_pos = 0;
    data_bit = 7;
}

static void add(uint8_t v)
{
    data[data_pos] |= (v << data_bit);

    data_bit--;
    if (data_bit < 0) {
        data_pos++;
        data_bit = 7;
    }
}

static void add_bit(uint8_t bit)
{
    // We are at 9Mhz, each bit is 0.111us
    // Thus, sending a zero is 0.111*4 = 0.44uS
    // and sending a one is 0.111*8 = 0.88uS

    if (bit) {
        add(1); add(1); add(1); add(1);
        add(1); add(1); add(1); add(1);
        add(0); add(0); add(0);
    } else {
        add(1); add(1); add(1);
        add(0); add(0); add(0); add(0);
        add(0); add(0); add(0); add(0);
    }
}

static void add_bits(uint8_t byte)
{
    for (int k=7; k>=0; k--) {
        add_bit((byte >> k)&1);
    }
}

static void DMAEvent()
{
    dma_disable(DMA1, DMA_CH5);
    dma_transmitting = false;
}


extern "C" 
{
void __irq_spi2()
{
    if (!dma_transmitting) {
        spi_irq_disable(spi.c_dev(), SPI_TXE_INTERRUPT);
    }
}
}

static void send_bits()
{
    // We write to the SPI
    tube_config.tube_dst = &spi.c_dev()->regs->DR;
    tube_config.tube_dst_size = DMA_SIZE_8BITS;

    // From the data buffer
    tube_config.tube_src = data;
    tube_config.tube_src_size = DMA_SIZE_8BITS;

    // We write data_pos values
    tube_config.tube_nr_xfers = data_pos;

    // Incremental position, complete and error interrupts enabled
    tube_config.tube_flags = DMA_CFG_SRC_INC | DMA_CFG_CMPLT_IE | DMA_CFG_ERR_IE;

    // There is no target data
    tube_config.target_data = NULL;

    // Driven by the SPI2 transfer ready interrupt
    tube_config.tube_req_src = DMA_REQ_SRC_SPI2_TX;

    dma_tube_cfg(DMA1, DMA_CH5, &tube_config);
    dma_set_priority(DMA1, DMA_CH5, DMA_PRIORITY_VERY_HIGH);
    dma_attach_interrupt(DMA1, DMA_CH5, DMAEvent);
    // spi_irq_enable(spi.c_dev(), SPI_TXE_INTERRUPT);
    dma_transmitting = true;
    dma_enable(DMA1, DMA_CH5);
    spi_tx_dma_enable(spi.c_dev());
}

void led_update()
{
    if (dma_transmitting) {
        return;
    }

    reset_bits();
    add_bits(led1_g);
    add_bits(led1_r);
    add_bits(led1_b);

    add_bits(led1b_g);
    add_bits(led1b_r);
    add_bits(led1b_b);

    add_bits(led2_g);
    add_bits(led2_r);
    add_bits(led2_b);

    add_bits(led2b_g);
    add_bits(led2b_r);
    add_bits(led2b_b);

    add_bits(led3_g);
    add_bits(led3_r);
    add_bits(led3_b);

    add_bits(led3b_g);
    add_bits(led3b_r);
    add_bits(led3b_b);

    data_pos += 16;

    send_bits();
}

void leds_init()
{
    spi.begin(SPI_9MHZ, MSBFIRST, 0);
    dma_init(DMA1);

    breathPhase = 0;
    breathPhase2 = 0;
    breathPhase3 = 0;
    breath.addPoint(0, 0);
    breath.addPoint(0.5, 100);
    breath.addPoint(1, 0);
}

char leds_are_custom()
{
    return mode == LEDS_CUSTOM;
}

char leds_are_blinking()
{
  return mode == LEDS_BLINK;
}

char leds_are_bad()
{
  return mode == LEDS_BAD;
}

void leds_decustom()
{
    mode = LEDS_BREATH;
}

void led_set(int index, int value, bool custom)
{
    if (custom) {
        mode = LEDS_CUSTOM;
    }

    led_set_all(value);
}

void led_set_mode(int mode_)
{
    if (mode_ == mode){
      return;
    }

    mode = mode_;
    if(mode == LEDS_BAD)
    {
        led_set_all(0xff0000, false);
        led_set_blink_duration(bad_leds_blink_duration);
    }

    if (mode == LEDS_BLINK || mode == LEDS_BAD){
        blink_start_time = millis();
        leds_max.u1.r = led1_r;
        leds_max.u1.g = led1_g;
        leds_max.u1.b = led1_b;
        leds_max.d1.r = led1b_r;
        leds_max.d1.g = led1b_g;
        leds_max.d1.b = led1b_b;

        leds_max.u2.r = led2_r;
        leds_max.u2.g = led2_g;
        leds_max.u2.b = led2_b;
        leds_max.d2.r = led2b_r;
        leds_max.d2.g = led2b_g;
        leds_max.d2.b = led2b_b;

        leds_max.u3.r = led3_r;
        leds_max.u3.g = led3_g;
        leds_max.u3.b = led3_b;
        leds_max.d3.r = led3b_r;
        leds_max.d3.g = led3b_g;
        leds_max.d3.b = led3b_b;
    }
}

void led_set_all(int value, bool custom)
{
    if (custom) {
        mode = LEDS_CUSTOM;
    }

    led1_r = led2_r = led3_r = (value>>16)&0xff;
    led1_g = led2_g = led3_g = (value>>8)&0xff;
    led1_b = led2_b = led3_b = (value>>0)&0xff;

    led1b_r = led2b_r = led3b_r = (value>>16)&0xff;
    led1b_g = led2b_g = led3b_g = (value>>8)&0xff;
    led1b_b = led2b_b = led3b_b = (value>>0)&0xff;
    led_update();
}

void led_all_color_set(int r, int g, int b) {
    mode = LEDS_CUSTOM;
    led1_r = led2_r = led3_r = led1b_r = led2b_r = led3b_r = r;
    led1_g = led2_g = led3_g = led1b_g = led2b_g = led3b_g = g;
    led1_b = led2_b = led3_b = led1b_b = led2b_b = led3b_b = b;
    led_update();
}

void led_color_set(int index, int r, int g, int b) {
  mode = LEDS_CUSTOM;
  switch (index) {
        case 1:
        led1_r = r;
        led1_g = g;
        led1_b = b;
        break;
        case 2:
        led2_r = r;
        led2_g = g;
        led2_b = b;
        break;
        case 3:
        led3_r = r;
        led3_g = g;
        led3_b = b;
        break;
        case 4:
        led1b_r = r;
        led1b_g = g;
        led1b_b = b;
        break;
        case 5:
        led2b_r = r;
        led2b_g = g;
        led2b_b = b;
        break;
        case 6:
        led3b_r = r;
        led3b_g = g;
        led3b_b = b;
        break;
    }
    led_update();
}

void led_stream_state()
{
    // XXX: Stream LEDs status
    //    rhock_stream_append();
}

void leds_tick()
{
    if (mode == LEDS_BREATH) {
        breathPhase += 0.0004;
        breathPhase2 += 0.0007;
        breathPhase3 += 0.0009;

        if (breathPhase > 1) {
            breathPhase = 0;
        }
        if (breathPhase2 > 1) {
            breathPhase2 = 0;
        }
        if (breathPhase3 > 1) {
            breathPhase3 = 0;
        }

        int v1 = breath.getMod(breathPhase);
        int v2 = breath.getMod(breathPhase2);
        int v3 = breath.getMod(breathPhase3);

        led1_r = led2_r = led3_r = led1b_r = led2b_r = led3b_r = v1;
        led1_g = led2_g = led3_g = led1b_g = led2b_g = led3b_g = v2;
        led1_b = led2_b = led3_b = led1b_b = led2b_b = led3b_b = v3;

    } else if (mode == LEDS_BLINK || mode == LEDS_BAD){
        float dt = millis() - blink_start_time;
        if (blink_increasing){
            if(2*dt > blink_duration){
                blink_increasing = false;
            } else {
                float coeff = 2*dt/blink_duration;

                led1_r = coeff * leds_max.u1.r;
                led1_g = coeff * leds_max.u1.g;
                led1_b = coeff * leds_max.u1.b;
                led1b_r = coeff * leds_max.d1.r;
                led1b_g = coeff * leds_max.d1.g;
                led1b_b = coeff * leds_max.d1.b;

                led2_r = coeff * leds_max.u2.r;
                led2_g = coeff * leds_max.u2.g;
                led2_b = coeff * leds_max.u2.b;
                led2b_r = coeff * leds_max.d2.r;
                led2b_g = coeff * leds_max.d2.g;
                led2b_b = coeff * leds_max.d2.b;

                led3_r = coeff * leds_max.u3.r;
                led3_g = coeff * leds_max.u3.g;
                led3_b = coeff * leds_max.u3.b;
                led3b_r = coeff * leds_max.d3.r;
                led3b_g = coeff * leds_max.d3.g;
                led3b_b = coeff * leds_max.d3.b;
            }
        } else {
            if(dt > blink_duration){
                blink_increasing = true;
                blink_start_time = millis();
            } else {
                float coeff = 2*(1-dt/blink_duration);

                led1_r = coeff * leds_max.u1.r;
                led1_g = coeff * leds_max.u1.g;
                led1_b = coeff * leds_max.u1.b;
                led1b_r = coeff * leds_max.d1.r;
                led1b_g = coeff * leds_max.d1.g;
                led1b_b = coeff * leds_max.d1.b;

                led2_r = coeff * leds_max.u2.r;
                led2_g = coeff * leds_max.u2.g;
                led2_b = coeff * leds_max.u2.b;
                led2b_r = coeff * leds_max.d2.r;
                led2b_g = coeff * leds_max.d2.g;
                led2b_b = coeff * leds_max.d2.b;

                led3_r = coeff * leds_max.u3.r;
                led3_g = coeff * leds_max.u3.g;
                led3_b = coeff * leds_max.u3.b;
                led3b_r = coeff * leds_max.d3.r;
                led3b_g = coeff * leds_max.d3.g;
                led3b_b = coeff * leds_max.d3.b;
            }
        }
    }

    led_update();
}

#define PACK_RGB(r,g,b) ((r<<16)|(g<<8)|(b))

int led_get(int index)
{
    switch (index) {
        case 0: return PACK_RGB(led1_r, led1_g, led1_b);
        case 1: return PACK_RGB(led1b_r, led1b_g, led1b_b);
        case 2: return PACK_RGB(led2_r, led2_g, led2_b);
        case 3: return PACK_RGB(led2b_r, led2b_g, led2b_b);
        case 4: return PACK_RGB(led3_r, led3_g, led3_b);
        case 5: return PACK_RGB(led3b_r, led3b_g, led3b_b);
    }

    return 0;
}

void led_reset_all()
{
    led_set_all(0, true);
}

void led_set_blink_duration(int duration)
{
    blink_duration = duration;
}

#ifdef DEBUG
TERMINAL_COMMAND(ld, "Test")
{
    mode = LEDS_CUSTOM;
    int led = atoi(argv[0]);
    if (led == 1) {
        led1b_r = led1_r = atoi(argv[1]);
        led1b_g = led1_g = atoi(argv[2]);
        led1b_b = led1_b = atoi(argv[3]);
    }
    if (led == 2) {
        led2b_r = led2_r = atoi(argv[1]);
        led2b_g = led2_g = atoi(argv[2]);
        led2b_b = led2_b = atoi(argv[3]);
    }
    if (led == 3) {
        led3b_r = led3_r = atoi(argv[1]);
        led3b_g = led3_g = atoi(argv[2]);
        led3b_b = led3_b = atoi(argv[3]);
    }

    led_update();
}

TERMINAL_COMMAND(led_bad, "Leds bad mode")
{
  led_set_mode(LEDS_BAD);
}

TERMINAL_COMMAND(ledColorSet, "test the leds") {
  led_color_set(atoi(argv[0]), atoi(argv[1]), atoi(argv[2]), atoi(argv[3]));
  terminal_io()->print("setting led ");
  terminal_io()->print(atoi(argv[0]));
  terminal_io()->print(" to ");
  terminal_io()->print(atoi(argv[1]));
  terminal_io()->print(" ");
  terminal_io()->print(atoi(argv[2]));
  terminal_io()->print(" ");
  terminal_io()->println(atoi(argv[3]));
}

TERMINAL_COMMAND(ledsBlink, "test blink mode") {
  if(argc == 0){
    terminal_io()->println("Usage : ledsBlink blink_duration");
    terminal_io()->println("If blink_duration is zero it stops the blinking.");
  }
  if (argv[0] == 0){
    led_set_mode(LEDS_CUSTOM);
  } else {
    led_set_mode(LEDS_BLINK);
    led_set_blink_duration(atoi(argv[0]));
  }
}

TERMINAL_COMMAND(leds, "test the leds") {
    if (argc >= 3) {
        led_all_color_set(atoi(argv[0]), atoi(argv[1]), atoi(argv[2]));
    } else {
        led_set_mode(LEDS_BREATH);
    }
}
#endif
