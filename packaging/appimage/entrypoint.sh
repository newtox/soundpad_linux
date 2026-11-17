if [ -z "${SOUNDPAD_LINUX_KEEP_QT_THEME:-}" ]; then
    export QT_QPA_PLATFORMTHEME=xdgdesktopportal
fi
exec {{ python-executable }} -s -m soundpad_linux "$@"
