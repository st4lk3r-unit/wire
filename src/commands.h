#pragma once
#include "konsole.h"

#ifdef __cplusplus
extern "C" {
#endif

int cmd_receive(struct konsole* ks, int argc, char** argv);
int cmd_send(struct konsole* ks, int argc, char** argv);

#ifdef __cplusplus
}
#endif
