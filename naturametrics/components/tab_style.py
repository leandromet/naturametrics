"""Style of the results tabs on every page: solid chips that wrap (no imports, so any component can use it)."""

# Solid chips that wrap onto a second row when the names do not fit one (a phone, or many tabs). The
# triggers carry their full name as a title (hover). Shared by every page's results tabs.
TAB_CHIP = {
    "height": "auto", "minHeight": "2.2rem", "padding": "0.3rem 0.7rem", "borderRadius": "6px",
    "background": "var(--gray-3)", "color": "var(--gray-12)", "border": "1px solid var(--gray-5)",
    "whiteSpace": "nowrap", "cursor": "pointer",
    "&::before": {"display": "none"},
    "&:hover": {"background": "var(--gray-4)"},
    "&[data-state='active']": {"background": "var(--accent-9)", "color": "white",
                               "borderColor": "var(--accent-9)"},
}
TAB_LIST = {"display": "flex", "flexWrap": "wrap", "gap": "6px", "boxShadow": "none", "height": "auto",
            "maxWidth": "100%", "paddingTop": "0.2rem", "paddingBottom": "0.4rem"}
