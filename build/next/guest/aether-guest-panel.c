#include <gtk/gtk.h>
#include <unistd.h>

static GtkWidget *entry, *resolution;
static void update_resolution(GdkScreen *screen, gpointer unused) {
    (void)unused;
    char *s = g_strdup_printf("Screen size: %d × %d", gdk_screen_get_width(screen), gdk_screen_get_height(screen));
    gtk_label_set_text(GTK_LABEL(resolution), s); g_free(s);
}
static void copy_text(GtkButton *button, gpointer unused) {
    (void)button; (void)unused;
    gtk_clipboard_set_text(gtk_clipboard_get(GDK_SELECTION_CLIPBOARD),
        gtk_entry_get_text(GTK_ENTRY(entry)), -1);
}
static void received_text(GtkClipboard *clipboard, const gchar *text, gpointer unused) {
    (void)clipboard; (void)unused;
    if (text) gtk_entry_set_text(GTK_ENTRY(entry), text);
}
static void paste_text(GtkButton *button, gpointer unused) {
    (void)button; (void)unused;
    gtk_clipboard_request_text(gtk_clipboard_get(GDK_SELECTION_CLIPBOARD), received_text, NULL);
}
static void terminal(GtkButton *button, gpointer unused) {
    (void)button; (void)unused;
    gchar *args[] = {"/usr/bin/xterm", "-fa", "DejaVu Sans Mono", "-fs", "11", NULL};
    g_spawn_async(NULL, args, NULL, 0, NULL, NULL, NULL, NULL);
}
int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), "Aether - Guest integration");
    gtk_window_set_default_size(GTK_WINDOW(window), 660, 410);
    gtk_window_set_position(GTK_WINDOW(window), GTK_WIN_POS_CENTER);
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 18);
    gtk_container_set_border_width(GTK_CONTAINER(box), 30);
    gtk_container_add(GTK_CONTAINER(window), box);
    GtkWidget *title = gtk_label_new(NULL);
    gtk_label_set_markup(GTK_LABEL(title), "<span size='xx-large' weight='bold'>Aether Linux</span>");
    gtk_widget_set_halign(title, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
    GtkWidget *subtitle = gtk_label_new("Guest integration session · 0.2.1 development");
    gtk_widget_set_halign(subtitle, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(box), subtitle, FALSE, FALSE, 0);
    GtkWidget *firmware = gtk_label_new(access("/sys/firmware/efi", F_OK) == 0 ?
        "Firmware: UEFI" : "Firmware: legacy BIOS");
    gtk_widget_set_halign(firmware, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(box), firmware, FALSE, FALSE, 0);
    resolution = gtk_label_new("");
    gtk_widget_set_halign(resolution, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(box), resolution, FALSE, FALSE, 0);
    GdkScreen *screen = gtk_widget_get_screen(window);
    update_resolution(screen, NULL);
    g_signal_connect(screen, "size-changed", G_CALLBACK(update_resolution), NULL);
    entry = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(entry), "Hello from Aether Linux");
    gtk_box_pack_start(GTK_BOX(box), entry, FALSE, FALSE, 0);
    GtkWidget *buttons = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    GtkWidget *copy = gtk_button_new_with_label("Copy text");
    GtkWidget *paste = gtk_button_new_with_label("Paste clipboard");
    GtkWidget *term = gtk_button_new_with_label("Open terminal");
    GtkWidget *end = gtk_button_new_with_label("End session");
    g_signal_connect(copy, "clicked", G_CALLBACK(copy_text), NULL);
    g_signal_connect(paste, "clicked", G_CALLBACK(paste_text), NULL);
    g_signal_connect(term, "clicked", G_CALLBACK(terminal), NULL);
    g_signal_connect_swapped(end, "clicked", G_CALLBACK(gtk_widget_destroy), window);
    gtk_box_pack_start(GTK_BOX(buttons), copy, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(buttons), paste, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(buttons), term, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(buttons), end, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), buttons, FALSE, FALSE, 0);
    GtkWidget *note = gtk_label_new("Enable clipboard sharing in your VM settings.\nResize the VM window to check automatic screen resizing.\nSelect End session to return to the console.");
    gtk_label_set_xalign(GTK_LABEL(note), 0);
    gtk_label_set_line_wrap(GTK_LABEL(note), TRUE);
    gtk_box_pack_start(GTK_BOX(box), note, FALSE, FALSE, 0);
    gtk_widget_show_all(window);
    gtk_main();
    return 0;
}
