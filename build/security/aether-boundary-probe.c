#include <errno.h>
#include <stdio.h>
#include <string.h>

/* A fixed-path test executable: success requires AppArmor to deny an otherwise
 * readable file, then allow a different file. No elevated file permissions. */
int main(void) {
    FILE *allowed = fopen("/tmp/aether-public-probe", "r");
    if (!allowed) { perror("public probe"); return 2; }
    fclose(allowed);
    FILE *denied = fopen("/tmp/aether-private-probe", "r");
    if (denied) { fclose(denied); puts("FAIL: private file readable"); return 3; }
    if (errno != EACCES) { perror("private probe unexpected error"); return 4; }
    puts("PASS: AppArmor allowed public access and denied private access");
    return 0;
}
