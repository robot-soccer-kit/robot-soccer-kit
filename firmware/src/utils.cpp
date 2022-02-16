#include "utils.h"
#include <Arduino.h>

float atof_nonan(char *str) {
  float result = atof(str);
  if (result != result) {
    return 0.;
  } else {
    return result;
  }
}