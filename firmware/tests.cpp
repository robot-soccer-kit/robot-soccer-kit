#include <stdlib.h>
#include <stdio.h>
#include "dc.h"
#include "delay.h"
#include "opticals.h"
#include "distance.h"
#include "buttons.h"
#include "bt.h"
#include "imu.h"
#include <terminal.h>

const char* SUCCESS = "SUCCESS";
const char* FAIL = "FAIL";
const char* END = "END";
const char* TODO = "TODO";

int delay_time = 500;

TERMINAL_COMMAND(test_motors, "Test for motors (incrementation and fails)."){
  terminal_io()->println("Testing motors.");
  int val = 2000;
  int min_encoder_value = 3000;
  int max_encoder_fails = 0;

  bool success = true;

  for(int sgn=-1 ; sgn <=1; sgn+=2){
    reset_encoder();
    volatile int* encoder_value = get_encoder_value();
    volatile int* encoder_fails = get_encoder_fails();

    dc_command(sgn*val, sgn*val, sgn*val);
    delay(delay_time);
    for (int k=0; k<3; k++){
      if(sgn*encoder_value[k] < min_encoder_value){
        if(success){
          terminal_io()->println(FAIL);
        }
        success = false;

        terminal_io()->print("Motor ");
        terminal_io()->print(k);
        terminal_io()->print(" not enough incrementation: ");
        terminal_io()->print(sgn*encoder_value[k]);
        terminal_io()->print(" >= ");
        terminal_io()->println(min_encoder_value);
      }
      if(encoder_fails[k]>max_encoder_fails){
        if(success){
          terminal_io()->println(FAIL);
        }
        success = false;

        terminal_io()->print("Motor ");
        terminal_io()->print(k);
        terminal_io()->print(" too much fails: ");
        terminal_io()->print(encoder_fails[k]);
        terminal_io()->print(" <= ");
        terminal_io()->println(max_encoder_fails);
        success = false;
      }
    }
  }
  dc_command(0, 0, 0);
  if(success){
    terminal_io()->println(SUCCESS);
  }
  terminal_io()->println(END);
}

// TERMINAL_COMMAND(test_optics, "Test optic board."){
//   terminal_io()->println("Testing opticals.");
//   int min_val = 1000;
//   int time = 2000;

//   bool success = false;

//   terminal_io()->println("Put a white surface in front off the opticals.");
//   delay(delay_time);
//   int opticals_min[7] = {10000,10000,10000,10000,10000,10000,10000};

//   int start = millis();
//   while(millis() - start < time){
//     opticals_tick();
//     show_opticals_raw_values();
//     for(int k=0; k<7; k++){
//       if(opticals[k] < opticals_min[k]){
//         opticals_min[k] = opticals[k];
//       }
//     }

//     bool flag = true;
//     for(int k=0; k<7; k++){
//       if(opticals_min[k] >= min_val){
//         flag = false;
//       }
//     }

//     if(flag){
//       success = true;
//       break;
//     }
//   }

//   if(success){
//     terminal_io()->println(SUCCESS);
//   }
//   else{
//     terminal_io()->println(FAIL);
//     for(int k=0; k<7; k++){
//       if(opticals_min[k] >= min_val){
//         terminal_io()->print("Optical");
//         terminal_io()->print(k);
//         terminal_io()->print(" not good: ");
//         terminal_io()->print(opticals_min[k]);
//         terminal_io()->print(" < ");
//         terminal_io()->println(min_val);
//       }
//     }
//   }
//   terminal_io()->println(END);
// }


TERMINAL_COMMAND(test_buttons, "Test buttons."){
  terminal_io()->println("Testing buttons");

  bool success = false;
  bool pushed[4] = {false, false, false, false};
  int pushed_threshold = 40;
  int time = 3000;

  terminal_io()->println("Push at least one time the four buttons.");
  delay(delay_time);
  int start = millis();
  while(millis() - start < time){
    bool flag = true;
    show_buttons_raw_values();
    for(int k=0; k<4; k++){
      if (not pushed[k]){
        if(get_button_raw_value(k) < pushed_threshold){
          pushed[k] = true;
        }
        else{
          flag = false;
        }
      }
    }

    if(flag){
      success = true;
      break;
    }
  }

  if(success){
    terminal_io()->println(SUCCESS);
  }
  else{
    terminal_io()->println(FAIL);
    for(int k=0; k<4; k++){
      if(not pushed[k]){
        terminal_io()->print("Button ");
        terminal_io()->print(k);
        terminal_io()->println(" was not pushed.");
      }
    }
  }
  terminal_io()->println(END);
}

bool touched = false;
TERMINAL_COMMAND(touch, "Used for tests."){
  touched = true;
}

TERMINAL_COMMAND(test_bluetooth, "Test bluetooth."){
  terminal_io()->println("Testing bluetooth.");

  bool success = false;
  int time = 1000;

  terminal_io()->println("You should try to send 'touch'");
  delay(delay_time);
  int start = millis();
  while(millis() - start < time){
    if(touched){
      success = true;
      break;
    }
  }
  touched = false;

  if(success){
    terminal_io()->println(SUCCESS);
  }
  else{
    terminal_io()->println(FAIL);
    terminal_io()->println("Bluetooth failed.");
  }
  terminal_io()->println(END);
}

TERMINAL_COMMAND(test_distance, "Test distance sensor."){
  terminal_io()->println("Testing distance sensor.");
  int time = 3000;

  bool success = false;
  bool short_distance = false;
  int short_threshold = 8;
  bool long_distance = false;
  int long_threshold = 30;
  bool empty_distance = false;
  int empty_threshold = 40;

  terminal_io()->println("Remove any obstacle.");
  delay(delay_time);
  int start = millis();
  while(millis() - start < time){
    show_distance();
    if(get_distance() > empty_threshold){
      empty_distance = true;
      break;
    }
  }

  terminal_io()->println("Put an obstacle the nearest possible to the robot.");
  delay(delay_time);
  start = millis();
  while(millis() - start < time){
    show_distance();
    if(get_distance() < short_threshold){
      short_distance = true;
      break;
    }
  }

  terminal_io()->println("Drive the obstacle away without removing it.");
  delay(delay_time);
  start = millis();
  while(millis() - start < time){
    show_distance();
    if(get_distance() > long_threshold){
      long_distance = true;
      break;
    }
  }

  if(short_distance && long_distance && empty_distance){
    success = true;
  }

  if(success){
    terminal_io()->println(SUCCESS); 
  }
  else{
    terminal_io()->println(FAIL); 
    if(not short_distance){
      terminal_io()->print("Short distance not below "); 
      terminal_io()->print(short_threshold); 
      terminal_io()->println("."); 
    }
    if(not long_distance){
      terminal_io()->print("Short distance not above "); 
      terminal_io()->print(long_threshold); 
      terminal_io()->println("."); 
    }
    if(not empty_distance){
      terminal_io()->print("Empty distance not above "); 
      terminal_io()->print(empty_threshold); 
      terminal_io()->println("."); 
    }
  }
  terminal_io()->println(END);
}

TERMINAL_COMMAND(test_imu, "Test imu."){
  terminal_io()->println("Testing imu.");

  bool success = true;
  int val = 0;

  // Get values
  for(int k=0; k<10; k++){
    delay(10);
    imu_tick();
    val = get_acc_norm();
    if(val > 282 || val < 230){
      success = false;
      break;
    }
  }
  if(success){
    terminal_io()->println(SUCCESS);
  }
  else{
    terminal_io()->println(FAIL);
    terminal_io()->print("Imu value is 230 <= ");
    terminal_io()->print(val);
    terminal_io()->print("<= 282.");
  }
  terminal_io()->println(END);
}

TERMINAL_COMMAND(test_buzzer, "Test buzzer."){
  terminal_io()->println("Testing buzzer.");


  terminal_io()->println(TODO);
}

TERMINAL_COMMAND(test_leds, "Test leds."){
  terminal_io()->println("Testing leds.");


  terminal_io()->println(TODO);
}

TERMINAL_COMMAND(test_charge, "Test charge."){
  terminal_io()->println("Testing charge.");


  terminal_io()->println(TODO);
}

TERMINAL_COMMAND(test_battery_empty, "Test battery empty."){
  terminal_io()->println("Testing battery empty.");


  terminal_io()->println(TODO);
}

TERMINAL_COMMAND(test_battery_full, "Test battery full."){
  terminal_io()->println("Testing battery full.");


  terminal_io()->println(TODO);
}
