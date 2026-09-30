#include <X11/Xlib.h>
#include <X11/XKBlib.h>

bool aetherCapsLockEnabled()
{
    struct Connection {
        Display *display = XOpenDisplay(nullptr);
        ~Connection() { if (display) XCloseDisplay(display); }
    };
    static Connection connection;
    XkbStateRec state{};
    return connection.display
        && XkbGetState(connection.display, XkbUseCoreKbd, &state) == Success
        && (state.locked_mods & LockMask);
}
