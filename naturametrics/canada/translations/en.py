"""English — canonical key set for the Canada page."""

from __future__ import annotations

TRANSLATIONS_EN: dict[str, str] = {
    # --- header / drawer ------------------------------------------------- #
    "nav_toggle_layers_aria": "Open layers panel",
    "nav_subtitle": "Crop inventory, forest age and forest change",
    "nav_title_suffix": "Canada",
    "drawer_title": "Layers and analysis",
    "drawer_close_aria": "Close panel",
    "go_to_brazil": "Go to Brazil",
    "language_label": "Language",
    "close_button": "Close",
    "clear_button": "Clear",
    "reset_button": "Reset",
    "cancel_button": "Cancel",

    # --- layer panel: sections -------------------------------------------- #
    "section_point": "Study point",
    "section_basemap": "Base map",
    "section_landcover": "Crop inventory (AAFC)",
    "section_buffer_preview": "Buffer land use",
    "buffer_preview_toggle_label": "Magnify crop inventory",
    "buffer_preview_text": (
        "Shows the most recent Annual Crop Inventory ({year}) only inside the "
        "analysis radius around the clicked point, and nowhere else. No Earth "
        "Engine call: the tiles are already loaded and the circle is a clip "
        "applied in the browser."
    ),
    "buffer_preview_hidden_note": (
        "Redundant while the full crop inventory layer is on \u2014 the coverage "
        "already shows across the whole map."
    ),
    "section_forest_age": "Forest age (NTEMS)",
    "section_forest_change": "Forest change (Hansen)",
    "section_landsat": "Landsat imagery",

    "year_label": "Year",
    "opacity_label": "Opacity",
    "aci_toggle_label": "Annual Crop Inventory",
    "aci_coverage_note": (
        "The Annual Crop Inventory is an agricultural product: it covers the "
        "settled south and stops at roughly 58°N. National coverage begins in "
        "2011 — 2009 and 2010 are the Prairies only."
    ),
    "aci_north_warning": (
        "This point is north of the crop inventory's extent, so the land-cover "
        "chart has nothing to show. Forest age and forest change cover all of "
        "Canada and are unaffected."
    ),

    "forest_age_toggle_label": "Stand age",
    "forest_age_note": (
        "Measured stand age from NTEMS, as of 2019 — not derived from a time "
        "series. Only forested pixels carry a value; everything else is "
        "transparent, which is the dataset saying “not forest” rather than "
        "“no data”."
    ),

    "forest_change_toggle_label": "Loss and gain",
    "change_base_year": "Loss from year",
    "change_loss_label": "Tree cover loss",
    "change_gain_label": "Tree cover gain",
    "treecover_threshold_label": "Forest threshold (canopy % in 2000)",
    "forest_change_note": (
        "Hansen Global Forest Change, 2001–2025. The year slider filters loss "
        "only: gain is published as a single undated flag for the whole record, "
        "so the green does not change as you move it."
    ),
    "hansen_treecover_toggle": "Tree cover 2000",

    "landsat_year_label": "Composite year",
    "landsat_note": (
        "One cloud-free Landsat composite per year, 1984–2026. Drawn over the "
        "base map chosen above."
    ),

    "point_click_other": "Click the map to choose another point.",
    "point_click_choose": "Click the map to choose a point.",

    "status_ee_unavailable": "Earth Engine unavailable",
    "status_ee_connecting": "Connecting to Earth Engine…",
    "status_ee_ready": "Earth Engine ready",

    # --- results ------------------------------------------------------------ #
    "landuse_title": "Crop inventory history",
    "analysis_running": "Reducing 17 years over 4 buffers…",
    "top_classes_title": "Top classes ({year})",
    "empty_state_title": "Click the map to choose a point",
    "empty_state_body": (
        "The crop-inventory history (2009–2025), forest stand age and Hansen "
        "forest change will be computed for radii of 1, 2, 5 and 10 km around "
        "it."
    ),
    "aci_empty_title": "No crop-inventory data here",
    "forest_age_title": "Forest age",
    "age_running": "Reading the NTEMS stand-age raster…",
    "age_median_label": "Median age band",
    "age_forest_area_label": "Forested area",
    "age_forest_pct_label": "Share of buffer that is forest",
    "age_reference_note": "Ages are as of {year}, the NTEMS reference year.",
    "age_point_label": "Age at the clicked pixel",
    "age_point_not_forest": "The clicked pixel is not forest",
    "age_years_unit": "years",
    "change_title": "Forest change {first}–{last}",
    "change_loss_ha": "Loss",
    "change_gain_ha": "Gain",
    "change_forest2000_ha": "Forest in 2000",
    "change_running": "Reading Hansen loss and gain…",
    "radius_label": "Radius",

    # --- export ------------------------------------------------------------- #
    "download_button": "Download data",
    "export_dialog_title": "Download data",
    "export_dialog_desc": (
        "An ODS spreadsheet with one tab per table and a metadata tab carrying "
        "the full provenance of every query. Opens in LibreOffice, Excel and "
        "Google Sheets."
    ),
    "export_point_desc": (
        "A spreadsheet with: the crop-inventory class of the clicked pixel year "
        "by year, one tab per radius ({radii} km) with the full 2009–2025 "
        "series, the forest age histogram, Hansen loss/gain, the AAFC class "
        "dictionary, and a metadata tab."
    ),
    "download_point_button": "Download point spreadsheet (.ods)",
    "download_point_hint": "Click a point on the map to enable this.",
    "export_choose_point_first": "Choose a point on the map first.",
    "export_stage_building": "Building the spreadsheet",
    "export_sheet_failed": "Failed to generate the spreadsheet: {exc}",
    "provenance_callout": (
        "No number leaves here without provenance: the metadata tab states "
        "which dataset, which bands, which scale and which reducer produced "
        "each table, and carries the attributions that must be cited."
    ),
    "no_point_badge": "no point",

    # --- errors -------------------------------------------------------------- #
    "err_coord_swapped": (
        "{point} is outside Canada, but {flipped} is inside — latitude and "
        "longitude look swapped."
    ),
    "err_coord_outside_canada": (
        "{point} is outside Canada. This page covers Canada only — use the "
        "Brazil page for South American coordinates."
    ),
    "err_earth_engine_query": "Earth Engine query failed: {exc}",
    "err_no_landcover": "No crop-inventory data found at this point.",
    "err_forest_failed": "Failed to read the forest data: {exc}",

    # --- help / cite --------------------------------------------------------- #
    "help_trigger": "How to use",
    "help_dialog_title": "How to use Naturametrics Canada",
    "help_dialog_desc": (
        "Crop-inventory history, forest stand age and forest change at any "
        "point in Canada."
    ),
    "help_step1_title": "Choose a point",
    "help_step1_body": (
        "Click anywhere in Canada. A marker is created and four analysis areas "
        "(1, 2, 5 and 10 km radius) are drawn around it. Clicks outside Canada "
        "are refused; clicks in the far north are not — see the note on "
        "coverage below."
    ),
    "help_step2_title": "Read the crop-inventory history",
    "help_step2_body": (
        "The chart below the map shows one column per year, 2009–2025, in the "
        "official AAFC legend colours. Switch the radius across 1/2/5/10 km and "
        "use the «%» button to toggle between hectares and area share."
    ),
    "help_step3_title": "Mind the coverage",
    "help_step3_body": (
        "The AAFC Annual Crop Inventory is an agricultural product, not a "
        "national land cover. It reaches roughly 58°N and no further, and its "
        "first two years (2009, 2010) cover only the Prairies. North of that "
        "limit the land-cover chart is empty while the forest panels still "
        "answer — the crop inventory simply does not extend there."
    ),
    "help_step4_title": "Read the forest age",
    "help_step4_body": (
        "NTEMS publishes a measured stand age for every forested pixel in "
        "Canada, as of 2019. The histogram bins the forested area of each "
        "buffer by age; the summary beside it gives the median band and how "
        "much of the buffer is forest at all. Pixels with no value are not "
        "forest, rather than missing."
    ),
    "help_step5_title": "Read the forest change",
    "help_step5_body": (
        "Hansen Global Forest Change gives tree-cover loss year by year from "
        "2001 to 2025, plus a gain flag. The «Forest threshold» control sets "
        "what canopy percentage in 2000 counts as forest — raise it to restrict "
        "the accounting to denser stands."
    ),
    "help_step6_title": "Switch the imagery",
    "help_step6_body": (
        "The Landsat section draws one cloud-free annual composite over the "
        "base map, in true colour or infrared false colour, for any year from "
        "1984 to 2026 — useful for seeing a clearing or a burn directly rather "
        "than through a classification."
    ),
    "help_step7_title": "Download the data",
    "help_step7_body": (
        "«Download data» produces an ODS spreadsheet with every table behind "
        "the charts and a metadata tab explaining how each number was computed."
    ),
    "help_limitations_title": "Limitations worth knowing",
    "help_limit_1": (
        "The crop inventory covers the agricultural south only, to roughly "
        "58°N, and is national only from 2011."
    ),
    "help_limit_2": (
        "Forest age is a 2019 snapshot. A stand reported as 40 years old is "
        "about 46 today; the app does not age the numbers forward, because "
        "that would invent precision the raster does not have."
    ),
    "help_limit_3": (
        "Hansen gain is undated — a single flag for 2000–2012 in the original "
        "product — so it cannot be filtered by year the way loss can."
    ),
    "help_limit_4": (
        "30 m resolution: a 1 km radius holds about 3,500 pixels, so a few "
        "misclassified pixels already move the percentages."
    ),

    "cite_trigger": "How to cite",
    "cite_dialog_title": "How to cite",
    "cite_dialog_desc": (
        "If Naturametrics Canada contributed to your work, cite it and also "
        "cite the data sources used."
    ),
    "cite_sources_title": "Data sources — cite these too",
    "cite_sources_desc": (
        "Each source has its own attribution requirements. When publishing "
        "figures or numbers obtained here, cite whichever ones were used."
    ),
}
