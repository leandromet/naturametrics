"""English overrides. Any key not listed here falls back to Portuguese."""

from __future__ import annotations

TRANSLATIONS_EN: dict[str, str] = {
    # --- header / drawer ------------------------------------------------- #
    "nav_toggle_layers_aria": "Open layers panel",
    "nav_subtitle": "Land-use history and landscape analysis",
    "drawer_title": "Layers and analysis",
    "drawer_close_aria": "Close panel",

    # --- layer panel: sections -------------------------------------------- #
    "section_basemap": "Base map",
    "section_landcover": "Land cover",
    "section_buffer_preview": "Buffer land use",
    "section_compare": "Compare two years",
    "section_change_mask": "Natural vegetation change",
    "section_ifn": "National Forest Inventory",
    "section_user_points": "Submitted coordinates",
    "section_multi_select": "Multiple selection",
    "section_biomes": "Biomes (IBGE)",
    "section_point": "Study point",

    "year_label": "Year",
    "opacity_label": "Opacity",
    "opacity_label_compare": "Opacity — right-hand year",
    "clear_button": "Clear",
    "reset_button": "Reset",

    "buffer_preview_toggle_label": "Show buffer land use",
    "buffer_preview_text": (
        "Hovering over a cluster — or choosing a point — shows MapBiomas "
        "only inside the analysis radius, for the year selected above. No "
        "Earth Engine call: it reuses the tiles already pre-loaded."
    ),
    "buffer_preview_hidden_note": (
        "Hidden while «MapBiomas 10.1» is on — the coverage already shows "
        "across the whole map."
    ),

    "compare_toggle_label": "Sliding curtain",
    "compare_year_left": "Left-hand year",
    "compare_opacity_left": "Opacity — left-hand year",
    "compare_note": (
        "Drag the white line on the map. The right side is the year "
        "selected above in «Land cover»."
    ),

    "change_mask_toggle_label": "Restoration candidates",
    "change_base_year": "Baseline year",
    "change_loss_label": "Natural vegetation loss",
    "change_gain_label": "Regrowth",
    "change_mask_callout": (
        "2008 is the Forest Code baseline: native vegetation cleared after "
        "that date carries a restoration obligation. This layer is a "
        "screening tool, not a formal report — it does not account for "
        "CAR, APP/RL, property size or clearing permits."
    ),

    "ifn_toggle_label": "Clusters",
    "filter_all": "All",
    "filter_region": "Region",
    "filter_biome": "Biome",
    "filter_uf": "State",
    "filter_municipality": "Municipality",
    "ifn_empty_callout": "No clusters match this filter combination.",
    "ifn_municipality_hint": "Choose a state to list municipalities.",
    "ifn_count_label_one": "cluster",
    "ifn_count_label_many": "clusters",

    "user_points_active_note": "Active on the map in place of the IFN clusters.",

    "multi_toggle_label": "Sum multiple clusters",
    "multi_help_text": (
        "Click clusters to add or remove them, or hold Ctrl (Cmd on Mac) "
        "and drag to select a whole area. The chart switches to the sum of "
        "areas for each radius. Shift+drag is still the map's area zoom, "
        "and single clicks are disabled while the mode is on."
    ),
    "multi_label_one": "Sum of 1 cluster",
    "multi_label_many": "Sum of {n} clusters",
    "multi_blocked_point_error": (
        "Multiple selection is on: click clusters to add or remove them. "
        "Turn the mode off to choose a single point."
    ),

    "biomes_toggle_label": "Biomes and domains",
    "biomes_hover_note": (
        "Hover over a polygon to see its biome, phytogeographic domain and "
        "natural region. Boundaries are simplified (~1 km) for browser "
        "rendering."
    ),

    "point_click_other": "Click the map to choose another point.",
    "point_click_choose": "Click the map to choose a point.",

    "basemap_unavailable": (
        "«{label}» unavailable — the account may not have accepted this "
        "dataset's license."
    ),

    "status_ee_unavailable": "Earth Engine unavailable",
    "status_ee_connecting": "Connecting to Earth Engine…",
    "status_ee_prefetching": "Pre-loading years… {done}/{total}",
    "status_ee_ready": "Earth Engine ready — {done} years cached",

    # --- results drawer ----------------------------------------------------- #
    "landuse_title": "Land-use history",
    "download_button": "Download data",
    "download_point_aria": "Download data for this point",
    "analysis_running": "Reducing 40 years over 4 buffers…",
    "top_classes_title": "Top classes (2024)",
    "area_natural_label": "Natural area (recorded)",
    "median_label": "Median (dated)",
    "no_change_label": "No change observed",
    "change_title": "Change 2008→2024",
    "vegetation_age_title": "Vegetation age",
    "age_running": "Reading the deforestation and secondary-vegetation series…",
    "empty_state_title": "Click the map to choose a point",
    "empty_state_body": (
        "The land-use history and vegetation age, from 1985/1987 to 2024, "
        "will be computed for radii of 1, 2, 5 and 10 km around it."
    ),

    # --- export dialog ------------------------------------------------------ #
    "export_dialog_title": "Download data",
    "export_dialog_desc": (
        "Each download is an ODS spreadsheet with one tab per table and a "
        "metadata tab with full provenance. Opens in LibreOffice, Excel "
        "and Google Sheets."
    ),
    "close_button": "Close",
    "no_point_badge": "no point",
    "study_point_desc": (
        "A spreadsheet with: the point's own pixel year by year, one tab "
        "per radius ({radii} km) with the full 1985–2024 series, a "
        "variation summary by class, the MapBiomas class dictionary, and "
        "a metadata tab with the provenance of each query."
    ),
    "download_point_button": "Download point spreadsheet (.ods)",
    "download_point_hint": "Click a point or a cluster on the map to enable this.",
    "selection_title_submitted": "Submitted list",
    "selection_title_default": "Cluster selection",
    "selection_note": (
        "Comes out point by point, one cluster per row — the sum shown in "
        "the chart is a reading, not the file's format."
    ),
    "check_points_label": "List of clusters",
    "check_points_detail": (
        "One per row: id, region, state, municipality, biome and "
        "coordinates. Instant."
    ),
    "check_pixel_label": "Pixel class, year by year",
    "check_pixel_detail": (
        "Each cluster's 30 m pixel, one column per year from 1985 to 2024. "
        "No size limit — the whole selection comes out in seconds."
    ),
    "check_buffers_label": "Buffer history ({radii} km)",
    "check_buffers_detail": (
        "Area by class and year, for each cluster — the same computation "
        "the chart does. One tab per radius. This is the expensive part: "
        "exporting a single radius makes the file much smaller and faster."
    ),
    "export_radii_label": "Radii to export",
    "cancel_button": "Cancel",
    "confirm_download_button": "Confirm and download",
    "download_selection_button": "Download selection spreadsheet (.ods)",
    "provenance_callout": (
        "No number leaves here without provenance: the «metadata» tab "
        "states which collection, which bands, which scale and which "
        "reducer produced each table, and carries the attributions that "
        "must be cited."
    ),
    "export_source_map_filters": "Map filters",
    "export_source_manual_prefix": "Manual selection",
    "export_selection_user_points": "{n} points from the submitted list",
    "export_selection_manual": "{n} clusters chosen on the map",
    "export_selection_whole_country": "All of Brazil (no filter)",
    "export_count_one": "cluster",
    "export_count_many": "clusters",
    "export_radius_all": "All radii",
    "export_no_selection": "No clusters in the current selection.",
    "export_choose_point_first": "Choose a point on the map first.",
    "export_stage_building_point": "Building the point spreadsheet",
    "export_stage_waiting_age": "Waiting for vegetation age…",
    "export_stage_computing_landuse": "Computing land use",
    "export_stage_computing_age": "Computing vegetation age",
    "export_stage_computing_change": "Computing 2008→2024 change",
    "export_stage_building_sheet": "Building the spreadsheet",
    "export_stage_gathering": "Gathering the clusters",
    "export_stage_reading_pixel": "Reading each cluster's pixel",
    "export_no_datasets": "Check at least one dataset.",
    "export_sheet_failed": "Failed to generate the spreadsheet: {exc}",
    "export_result_failed_note": " · {n} cluster(s) failed",

    # --- submit-coordinates dialog ------------------------------------------ #
    "send_button": "Submit data",
    "send_list_aria": "Submit coordinate list",
    "send_dialog_title": "Submit coordinate list",
    "send_dialog_desc": (
        "Paste a list of points — one per line — to use it on the map "
        "instead of the IFN clusters: hovering or clicking a point now "
        "refers to this list, and the full analysis for every point can "
        "be downloaded afterwards. Only pasted text is accepted, no file "
        "upload."
    ),
    "send_format_label": "Format: name (optional), latitude, longitude",
    "send_max_points": "Up to {max} points per list.",
    "send_active_points": "{n} active points",
    "send_truncated": (
        "The list has more than {max} valid points; only the first "
        "{max} were kept."
    ),
    "submit_button": "Submit",

    # --- coordinate validation ------------------------------------------ #
    "err_coord_swapped": (
        "{point} is outside Brazil, but {flipped} is inside — latitude "
        "and longitude look swapped."
    ),
    "err_coord_outside_brazil": (
        "{point} is outside Brazil. MapBiomas covers only Brazil, so there "
        "is no land-cover history for this location."
    ),

    # --- provenance line ----------------------------------------------------- #
    "years_unit": "years",
    "provenance_degraded": " · degraded result",
    "provenance_summed_one": " · sum of 1 cluster (overlapping buffers are counted in each)",
    "provenance_summed_many": " · sum of {n} clusters (overlapping buffers are counted in each)",

    # --- conglomerado hover card / multi-select -------------------------- #
    "hover_no_coverage": "No mapped coverage in this radius.",
    "hover_natural_template": "Natural vegetation {last}% (was {first}% in {year})",
    "hover_note_template": (
        "Composition in {year} within a {radius} km radius. Click for the "
        "full analysis."
    ),
    "hover_coords_unavailable": "Cluster coordinates unavailable.",
    "hover_read_failed": "Could not read the coverage here.",
    "multi_limit_reached": (
        "Limit of {max} clusters in the selection. Remove one to add "
        "another."
    ),
    "multi_analysis_failed": "Failed to analyze {key}: {exc}",
    "multi_area_none_new": "No new clusters in that area.",
    "multi_area_none": "No clusters in that area.",
    "multi_area_limit_reached": "Limit of {max} clusters reached.",
    "multi_area_truncated": (
        "Area has more clusters than the limit — the first {n} were "
        "included."
    ),
    "multi_area_failed": "{n} cluster(s) failed.",

    # --- analysis errors --------------------------------------------------- #
    "err_earth_engine_query": "Earth Engine query failed: {exc}",
    "err_no_landcover": "No land cover found for this point.",
    "err_vegetation_age_failed": "Failed to compute vegetation age: {exc}",
    "err_no_vegetation_age": "No vegetation age data for this point.",

    # --- language switcher ---------------------------------------------- #
    "language_label": "Language",
}
