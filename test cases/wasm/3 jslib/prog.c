#include <stdio.h>
#include <emscripten.h>

// This code should have a reference to the Javascript sampleFunction defined in the
// library file. I don't know how to write it so it does not do that.
//
// Patches welcome.

int main() {
  printf("Hello World\n");
  // sampleFunction(); ????
  return 0;
}
