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
    "filters_label": "Filters",
    "ifn_filters_title": "IFN filters",
    "section_user_points": "Submitted coordinates",
    "section_multi_select": "Multiple selection",
    "section_biomes": "Biomes (IBGE)",
    "section_point": "Study point",
    "buffer_square_toggle_label": "Use square buffers (side = diameter)",
    "buffer_caption_square": "(square side)",
    "buffer_caption_circle": "(circle radius)",
    "multi_shape_change_note": "Change the shape before selecting multiple points.",

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
    "multi_view_sum": "Sum",
    "multi_view_full_area": "Full area",
    "multi_full_area_failed": "Failed to compute the full area: {exc}",

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
    "full_area_running": "Reducing 40 years over the bounding box…",
    "top_classes_title": "Top classes (2024)",
    "area_natural_label": "Natural area (recorded)",
    "median_label": "Median (dated)",
    "no_change_label": "No change observed",
    "change_title": "Change 2008→2024",
    "vegetation_age_title": "Vegetation age",
    "landscape_metrics_tab": "Landscape metrics",
    "landscape_metrics_empty": "Metrics are not available yet.",
    "metrics_buffer": "Buffer",
    "metrics_area": "Area (ha)",
    "metrics_patches": "Patches",
    "metrics_patch_density": "Patches/ha",
    "metrics_lpi": "Largest patch (%)",
    "metrics_edge_density": "Edge (m/ha)",
    "metrics_shannon": "Shannon",
    "metrics_simpson": "Simpson",
    "metrics_evenness": "Evenness",
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
    "check_full_area_label": "Full area (bounding box)",
    "check_full_area_detail": (
        "One single box enclosing every selected cluster's buffer, with no "
        "overlap counted twice — but including the area between them too. "
        "Two extra tabs, land use and vegetation age. Manual selection only."
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
    "export_stage_computing_full_area": "Computing the full area",
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
    "provenance_full_area_one": " · full area of 1 cluster (bounding box, includes area between points)",
    "provenance_full_area_many": " · full area of {n} clusters (bounding box, includes area between points)",

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

    # --- "Como usar" dialog ------------------------------------------------ #
    "help_trigger": "How to use",
    "help_dialog_title": "How to use Naturametrics",
    "help_dialog_desc": (
        "Land-use history and landscape analysis at any point in Brazil."
    ),
    "help_step1_title": "Choose a point",
    "help_step1_body": (
        "Click anywhere on the map. A marker is created and four analysis "
        "areas (1, 2, 5 and 10 km radius) are drawn around it. Clicks "
        "outside Brazil are refused: MapBiomas covers only national "
        "territory."
    ),
    "help_step2_title": "Read the land-use history",
    "help_step2_body": (
        "The chart below the map shows one column per year, from 1985 to "
        "2024, with MapBiomas classes in their official colours. Switch "
        "the radius across 1/2/5/10 km and use the «%» button to toggle "
        "between hectares and area share."
    ),
    "help_step3_title": "Switch the base map",
    "help_step3_body": (
        "The default is Google's hybrid map, which shows municipality "
        "names and roads — useful for checking where you are. The list "
        "also includes Brazil's 2008 SPOT mosaic, in natural colour and "
        "infrared false colour: it covers only the country's forest "
        "areas, so there are gaps outside that footprint, and it is drawn "
        "on top of whichever base map was chosen before."
    ),
    "help_step4_title": "See the coverage on the map",
    "help_step4_body": (
        "Turn on «MapBiomas 10.1» in the sidebar. The «Year» control "
        "spans 1985–2024 — every year is pre-loaded, so switching is "
        "instant and the map does not shift. «Opacity» controls how much "
        "of the base map shows through underneath."
    ),
    "help_step5_title": "Compare two years",
    "help_step5_body": (
        "«Sliding curtain» shows two years at once, split by a white line "
        "you drag across the map. The left-hand year is chosen in its own "
        "panel; the right-hand one is the year selected in «Land cover». "
        "Each side has its own opacity."
    ),
    "help_step6_title": "Find restoration candidates",
    "help_step6_body": (
        "«Natural vegetation change» highlights in red what was natural "
        "vegetation in the baseline year and no longer is, and in green "
        "what has regrown. The default is 2008, the Forest Code baseline: "
        "clearing after 22/07/2008 carries a restoration obligation."
    ),
    "help_step7_title": "Work with the IFN clusters",
    "help_step7_body": (
        "Turn on «Clusters» in the sidebar to see the 17,479 points of "
        "the National Forest Inventory, and filter by region, biome, "
        "state and municipality — the map frames the selection on its "
        "own. Zooming in makes the points interactive: hover over one to "
        "see its coverage within a 10 km radius today and in 1985 — and "
        "the map itself shows MapBiomas only inside that radius, for the "
        "chosen year. Click to run the full analysis at its official "
        "coordinates."
    ),
    "help_step8_title": "Sum several clusters",
    "help_step8_body": (
        "Turn on «Multiple selection» in the sidebar and click the "
        "clusters you're interested in — clicking again removes them — "
        "or hold Ctrl (Cmd on Mac) and drag to grab a whole area at once. "
        "The chart switches to showing the summed area of each radius "
        "across all of them, and the map draws every buffer at once. "
        "Note: overlapping buffers are counted once per cluster, so the "
        "total is not the area of the union."
    ),
    "help_step9_title": "Download the data",
    "help_step9_body": (
        "Under «Download data», at the top of the page. There are two "
        "independent ODS spreadsheets: one for the current study point, "
        "with one tab per radius and the point's own pixel year by year; "
        "and one for the cluster selection — by the map's filters or by "
        "hand-picked points — where you mark what you want: point list, "
        "pixel class year by year, and buffer history — with one tab per "
        "radius, and the option to export a single radius, which fits "
        "many more clusters. Every spreadsheet opens with a «metadata» "
        "tab explaining how each number was computed."
    ),
    "help_triage_callout": (
        "This layer is a screening tool, not a formal report. It does "
        "not account for CAR, APP/Legal Reserve, property size or "
        "clearing permits. Use it to guide the investigation, not to "
        "conclude it."
    ),
    "help_limitations_title": "Limitations worth knowing",
    "help_limit_1": (
        "30 m resolution: a 1 km radius holds about 3,500 pixels, so a "
        "few misclassified pixels already move the percentages."
    ),
    "help_limit_2": (
        "The MapBiomas series starts in 1985 — there is no way to know "
        "the age of vegetation that already existed before then."
    ),
    "help_limit_3": (
        "Areas are computed from the pixel's real area "
        "(ee.Image.pixelArea), which varies with latitude; a fixed value "
        "of 0.09 ha would overestimate the area."
    ),
    "help_limit_4": (
        "MapBiomas classes are not colour-blind safe — the legend always "
        "carries the name next to the colour."
    ),

    # --- "Como citar" dialog ------------------------------------------------ #
    "cite_trigger": "How to cite",
    "cite_dialog_title": "How to cite",
    "cite_dialog_desc": (
        "If Naturametrics contributed to your work, cite it and also "
        "cite the data sources used."
    ),
    "cite_suggested_title": "Suggested citation",
    "cite_copy_citation": "Copy citation",
    "cite_bibtex_title": "BibTeX",
    "cite_copy_bibtex": "Copy BibTeX",
    "cite_authors_title": "Authors and institutions",
    "cite_sources_title": "Data sources — cite these too",
    "cite_sources_desc": (
        "Each source has its own attribution requirements. When "
        "publishing figures or numbers obtained here, cite whichever "
        "ones were used."
    ),
    "cite_example_title": "Example of use in text",
    "cite_example_body": (
        "\"The study area was analysed with Naturametrics (Biondo et al., "
        "2026), using MapBiomas Collection 10.1 and Hansen Global Forest "
        "Change data (Hansen et al., 2013).\""
    ),
    "cite_spot_callout": (
        "The SPOT 2008 imagery (Brazil Forest Imagery Dataset) requires "
        "accepting a specific Google license and is not yet enabled on "
        "this instance."
    ),

    # --- AI-disclaimer dialog ------------------------------------------------ #
    "ai_trigger": "AI use disclosure",
    "ai_dialog_desc": "How this application was built, and with what help.",
    "ai_para1": (
        "Naturametrics' code was written with the assistance of "
        "Anthropic's AI models — Claude Opus and Claude Sonnet — under "
        "the author's supervision and review at every step. The "
        "architecture, state patterns and most of the interface "
        "conventions come from Yvynation, an already-mature sibling "
        "platform for Indigenous-lands analysis, also built with the "
        "same process."
    ),
    "ai_para2": (
        "That means large parts of this application — from the Earth "
        "Engine integration to the interface components — were adapted "
        "or rewritten from what already worked in Yvynation, rather than "
        "built from scratch."
    ),
    "ai_see_yourself_title": "See for yourself",
    "ai_yvynation_link": "Yvynation — live application",

    # --- language switcher ---------------------------------------------- #
    "go_to_canada": "Go to Canada",
    "language_label": "Language",
}
