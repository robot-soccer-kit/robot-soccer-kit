// #define DEBUG
#include <stdlib.h>
#include <wirish/wirish.h>
#include <terminal.h>
#include <adc.h>
#include "mux.h"

// Current multiplexer address
static volatile int mux_addr = 0;

// The multiplexers pins are not in hardware.h because there is specific
// optimizations (see below)
#define MUX_ADDR1   20
#define MUX_ADDR2   18
#define MUX_ADDR3   7
#define MUX1        10  // ADC1 channel 1
#define MUX2        6   // ADC1 channel 5
#define MUX3        33  // ADC1 channel 9

__attribute__((always_inline)) inline int mux_read_1()
{
    return gpio_read_bit(GPIOA, 1) ? HIGH : LOW;
}
__attribute__((always_inline)) inline int mux_read_2()
{
    return gpio_read_bit(GPIOA, 5) ? HIGH : LOW;
}
__attribute__((always_inline)) inline int mux_read_3()
{
    return gpio_read_bit(GPIOB, 1) ? HIGH : LOW;
}
__attribute__((always_inline)) inline void mux_set_addr(int addr)
{
    mux_addr = addr;
    gpio_write_bit(GPIOA, 15, (addr>>0)&1);
    gpio_write_bit(GPIOB, 4, (addr>>1)&1);
    gpio_write_bit(GPIOA, 4, (addr>>2)&1);
}

#define MUX_REGISTERS 6

volatile struct muxs multiplexers;

struct mux_reg
{
    uint8_t addr;
    volatile int *value1;
    volatile int *value2;
    volatile int *value3;
};

// Definitions of the registers from the multiplexers
struct mux_reg mux_registers[MUX_REGISTERS] = {
    {2, &multiplexers.opticals[0], &multiplexers.opticals[1], &multiplexers.opticals[2]},
    {3, &multiplexers.opticals[3], &multiplexers.opticals[4], &multiplexers.opticals[5]},
    {4, &multiplexers.opticals[6], &multiplexers.buttons[0], &multiplexers.buttons[1]},
    {5, &multiplexers.buttons[2], &multiplexers.buttons[3], &multiplexers.voltage1},
    {6, &multiplexers.distance, &multiplexers.dummy, &multiplexers.dummy},
    {7, &multiplexers.voltage2, &multiplexers.in1, &multiplexers.in2},
};

// Are we reading encoders or values ?
volatile int mux_sequence = 0;

// Which one of the values are we reading ?
volatile int mux_register = 0;

// Which multiplexed are we sampling from ?
volatile int adc_reading = -1;

// To remove (debug)
TERMINAL_PARAMETER_INT(oops, "OOps", 0);

extern "C" {
// Sampling the 3 channels sequentially based on interrupts
// This is triggered at 24Khz (each 41.6us)
// There is 6 different groups of sensors to read, so all the sensors
// are sampled at 4khz
extern void __irq_adc(void)
{
    // Clearing End Of Conversion flag
    volatile uint16 sample = (uint16)(ADC1->regs->DR & ADC_DR_DATA);

    if (adc_reading >= 0) {
        if (adc_reading == 0) {
            // Ignore this value, this is a trick to wait for ~8us and be
            // sure that the multiplexers switched to the correct address
            adc_reading = MUX1;
            analogReadRun(MUX2);
        } else if (adc_reading == MUX1) {
            *mux_registers[mux_register].value2 = sample;
            adc_reading = MUX2;
            analogReadRun(MUX3);
        }  else if (adc_reading == MUX2) {
            *mux_registers[mux_register].value3 = sample;
            adc_reading = MUX3;
            analogReadRun(MUX1);
        } else if (adc_reading == MUX3) {
            *mux_registers[mux_register].value1 = sample;
            // Preparing to read the encoders
            adc_reading = -1;
            mux_set_addr(0);
        } else {
            adc_reading = -1;
        }
    }
}
}

bool mux_tick()
{
    if (adc_reading > 0) {
        oops++;
        return false;
    }

    // Reading from the encoders
    multiplexers.p1a = mux_read_1();
    multiplexers.p1b = mux_read_2();
    multiplexers.p2a = mux_read_3();

    mux_set_addr(1);
    delay_us(1);
    asm volatile("nop;nop;nop;nop;nop;nop;nop;nop;nop;nop;");
    asm volatile("nop;nop;nop;nop;nop;nop;nop;nop;nop;nop;");
    asm volatile("nop;nop;nop;nop;nop;nop;nop;nop;nop;nop;");
    asm volatile("nop;nop;nop;nop;nop;nop;nop;nop;nop;nop;");
    asm volatile("nop;nop;nop;nop;nop;");

    multiplexers.p2b = mux_read_1();
    multiplexers.p3a = mux_read_2();
    multiplexers.p3b = mux_read_3();
    // Setting address to next register
    mux_register++;
    if (mux_register >= MUX_REGISTERS) {
        mux_register = 0;
    }
    mux_set_addr(mux_registers[mux_register].addr);

    if (mux_registers[mux_register].addr == 6) {
        // opticals_cycle();
    }

    // Running the first sampling
    adc_reading = 0;
    analogReadRun(MUX1);

    // We just read the encoders
    return true;
}

void mux_init()
{
    // Initializing pins
    mux_set_addr(0);
    pinMode(MUX_ADDR1, OUTPUT);
    pinMode(MUX_ADDR2, OUTPUT);
    pinMode(MUX_ADDR3, OUTPUT);
    pinMode(MUX1, INPUT_FLOATING);
    pinMode(MUX2, INPUT_FLOATING);
    pinMode(MUX3, INPUT_FLOATING);

    // Initalizing pins of quadrature phases
    multiplexers.p1a = 0;
    multiplexers.p1b = 0;
    multiplexers.p2a = 0;
    multiplexers.p2b = 0;
    multiplexers.p3a = 0;
    multiplexers.p3b = 0;

    // Enabling adc interrupt
    nvic_irq_enable(NVIC_ADC_1_2);
}

#ifdef DEBUG

TERMINAL_COMMAND(bet, "Bench tick")
{
    int maxdur = 0;
    int avg = 0;
    for (int k=0; k<100; k++) {
        int start = micros();
        mux_tick();
        int dur = micros()-start;
        avg += dur;
        if (dur > maxdur) maxdur = dur;
        delay_us(300);
        terminal_io()->println(dur);
    }
    terminal_io()->println("Max:");
    terminal_io()->println(maxdur);
    avg /= 100;
    terminal_io()->println("Avg:");
    terminal_io()->println(avg);
}

TERMINAL_COMMAND(mux, "Mux dbg")
{
    while (!SerialUSB.available()) {
        for (int k=0; k<11; k++) {
            terminal_io()->print("Optical ");
            terminal_io()->print(k);
            terminal_io()->print(": ");
            terminal_io()->println(multiplexers.opticals[k]);
        }
        terminal_io()->print("Distance ");
        terminal_io()->print(": ");
        terminal_io()->println(multiplexers.distance);
        terminal_io()->print("Voltage1: ");
        terminal_io()->println(multiplexers.voltage1);
        terminal_io()->print("Voltage2: ");
        terminal_io()->println(multiplexers.voltage2);

        terminal_io()->println("-");
        delay(20);
    }
}
#endif
