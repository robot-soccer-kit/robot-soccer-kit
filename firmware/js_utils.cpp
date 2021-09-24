#ifdef __EMSCRIPTEN__
#include "js_utils.h"
#include <emscripten.h>
unsigned int millis()
{
  return EM_ASM_INT({
      return (new Date()).getTime()%0xffffffff;
    }, 0);
}
#endif
