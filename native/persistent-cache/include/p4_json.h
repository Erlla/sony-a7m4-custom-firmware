#ifndef M4_P4_JSON_H
#define M4_P4_JSON_H
#include <stdint.h>

#define P4_JSON_MAX_BYTES 131072u
#define P4_JSON_WORKSPACE_BYTES 12288u
#define P4_JSON_ENVELOPE_MAX 8398u
#define P4_JSON_ENGINE_ABI 0x00020000u

enum p4_json_error {
 P4J_OK=0, P4J_ARGUMENT=-1, P4J_SIZE=-2, P4J_SYNTAX=-3,
 P4J_DEPTH=-4, P4J_UTF8=-5, P4J_FIELDS=-6, P4J_RANGE=-7,
 P4J_IDENTITY=-8, P4J_HASH=-9, P4J_DRAFT=-10, P4J_NATIVE=-11,
 P4J_TARGET=-12, P4J_COMPLEXITY=-13
};

typedef struct p4_json_result {
 uint8_t uuid[16];
 uint32_t revision;
 uint8_t content_sha256[32], file_sha256[32];
 char name[64];
 uint32_t name_bytes, grid_mode, envelope_bytes;
 uint8_t diagonal_domains[24];
 uint8_t envelope[P4_JSON_ENVELOPE_MAX];
} p4_json_result;

/* Production-only camera-look v2 compiler: rejects draft, validates complete
 * native photo/live and requires every D domain to include1024 and2048.
 * Input is immutable. No IO/OS/heap/global mutable state/pointer retention.
 * workspace needs P4_JSON_WORKSPACE_BYTES bytes, any alignment; workspace,
 * output and input must be disjoint. On failure output remains byte-for-byte
 * unchanged; workspace is unspecified scratch. Result contains an internal
 * P3 envelope, never an additional SD format. Metadata has no fit claims.
 * Caller must serialize mutation of input for the duration of this call.
 */
int32_t p4_json_compile(const uint8_t *input, uint32_t input_bytes,
                       void *workspace, uint32_t workspace_bytes,
                       p4_json_result *output);
void p4_json_sha256(const uint8_t *input, uint32_t bytes, uint8_t output[32]);
#endif
