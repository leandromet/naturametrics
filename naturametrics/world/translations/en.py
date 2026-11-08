"""English — canonical key set for the world page."""

from __future__ import annotations

TRANSLATIONS_EN: dict[str, str] = {
    'nav_toggle_layers_aria': 'Open layers panel',
    'nav_subtitle': 'Land-cover history, disturbance and forest change — anywhere on Earth',
    'nav_title_suffix': 'World',
    'drawer_title': 'Layers and analysis',
    'drawer_close_aria': 'Close panel',
    'results_resize_aria': 'Resize the results panel',
    'results_resize_label': 'Resize',
    'results_resize_hint': "Cycles the panel's height between compact, half, and expanded.",
    'legend_title': 'Legend',
    'legend_collapse_aria': 'Collapse the legend',
    'legend_expand_aria': 'Expand the legend',
    'go_to_brazil': 'Go to Brazil',
    'language_label': 'Language',
    'close_button': 'Close',
    'search_title': 'Find a place',
    'search_placeholder': 'Address, coordinate or place…',
    'search_read_as': 'read as:',
    'search_button': 'Search',
    'search_button_busy': 'Searching…',
    'search_clear_aria': 'Clear the search',
    'search_places_heading': 'Places and addresses',
    'search_places_note': (
        'A place only frames the map and drops a pin. Click the map to choose an '
        'analysis point.'
    ),
    'search_place_hint': 'click the map to choose an analysis point',
    'echo_postal': 'postal code',
    'echo_coordenada': 'coordinate',
    'echo_lugar': 'place',
    'erro_postal_nao_encontrado': 'Postal code {code} not found. Try the street address instead.',
    'erro_lugar_nao_encontrado': 'No place found for “{query}”.',
    'precision_endereco': 'address',
    'precision_rua': 'street',
    'precision_cep': 'postal code',
    'precision_bairro': 'neighbourhood',
    'precision_cidade': 'town',
    'precision_regiao': 'region',
    'precision_lugar': 'place',
    'qs_title': 'Get started in 30 seconds',
    'qs_step1_lead': 'Search',
    'qs_step1_body': 'a street address, coordinate or place — or just pan the map.',
    'qs_step2_lead': 'Click any point',
    'qs_step2_body': 'anywhere on the map, from 60°S to 85°N: a marker and five analysis areas are drawn around it.',
    'qs_step3_lead': 'Read the results',
    'qs_step3_body': 'below the map: land-cover history (GLC-FCS30D) and forest loss and gain.',
    'qs_step4_lead': 'Download the data',
    'qs_step4_body': 'from «Download data» at the top of the page.',
    'qs_more': (
        'There is much more: yearly Landsat imagery, forest-change layers, a '
        'preview of the analysis areas and species records (GBIF).'
    ),
    'qs_got_it': 'Got it',
    'qs_full_howto': 'See the full how-to',
    'qs_close_aria': 'Close the quick start',
    'help_show_quickstart': 'Show the quick start again',
    'clear_button': 'Clear',
    'reset_button': 'Reset',
    'cancel_button': 'Cancel',
    'section_point': 'Study point',
    'section_basemap': 'Base map',
    'section_landcover': 'Land cover (GLC-FCS30D)',
    'section_buffer_preview': 'Buffer land use',
    'buffer_preview_toggle_label': 'Magnify land cover',
    'buffer_preview_text': 'Shows the most recent GLC-FCS30D year ({year}) only inside the analysis radius around the clicked point, and nowhere else. It makes no Earth Engine call: the tiles are already loaded and the circle is a clip applied in the browser.',
    'buffer_preview_hidden_note': 'Redundant while the full GLC-FCS30D layer is on — the coverage is already drawn across the whole map.',
    'section_forest_change': 'Forest change (Hansen)',
    'section_landsat': 'Landsat imagery',
    'year_label': 'Year',
    'opacity_label': 'Opacity',
    'forest_change_toggle_label': 'Loss and gain',
    'change_base_year': 'Loss from year',
    'change_loss_label': 'Tree cover loss',
    'change_gain_label': 'Tree cover gain',
    'treecover_threshold_label': 'Forest threshold (canopy % in 2000)',
    'forest_change_note': (
        'Hansen Global Forest Change, 2001–2025. The year slider filters loss only: '
        'gain is published as a single undated flag for the whole record, so the '
        'green does not change as you move it.'
    ),
    'hansen_treecover_toggle': 'Tree cover 2000',
    'landsat_year_label': 'Composite year',
    'landsat_note': (
        'One cloud-free Landsat composite per year, 1984–2026. Drawn over the base '
        'map chosen above.'
    ),
    'point_click_other': 'Click the map to choose another point.',
    'point_click_choose': 'Click the map to choose a point.',
    'status_ee_unavailable': 'Earth Engine unavailable',
    'status_ee_connecting': 'Connecting to Earth Engine…',
    'status_ee_ready': 'Earth Engine ready',
    'section_gbif': 'Species occurrences',
    'gbif_toggle_label': 'GBIF — occurrence records',
    'gbif_info': (
        'Species occurrence records from GBIF (Global Biodiversity Information '
        'Facility). They appear from zoom 10 only — further out, a single point is '
        'smaller than a pixel. The layer shows at most 300 records per view; use '
        'the search to narrow what you want.'
    ),
    'gbif_zoom_note': 'Zoom in to level 10 or closer to see the records.',
    'gbif_truncated_note': 'records in this view — narrow the search',
    'gbif_taxonomy_group': 'Taxon',
    'gbif_records_group': 'Record type and year',
    'gbif_taxonomy_title': 'Browse the classification',
    'gbif_rank_kingdom': 'Kingdom',
    'gbif_rank_phylum': 'Phylum',
    'gbif_rank_class': 'Class',
    'gbif_rank_order': 'Order',
    'gbif_rank_family': 'Family',
    'gbif_rank_genus': 'Genus',
    'gbif_rank_species': 'Species',
    'gbif_name_label': 'Scientific name',
    'gbif_name_placeholder': 'e.g. Ursus arctos, Picea glauca…',
    'gbif_basis_label': 'Basis of record',
    'gbif_year_label': 'Event year',
    'gbif_province_label': 'Country',
    'gbif_buffers_run': 'List species',
    'gbif_buffers_no_point': 'Pick a point on the map to list the species recorded around it.',
    'gbif_records_word': 'records',
    'gbif_species_word': 'species',
    'gbif_top_species': 'Most-recorded species',
    'gbif_show_zone_hint': 'Show this ring on the map',
    'landuse_title': 'Land-cover history',
    'analysis_running': 'Processing 17 years over 5 buffers…',
    'top_classes_title': 'Top classes ({year})',
    'empty_state_title': 'Click the map to choose a point',
    'empty_state_body': 'The land-cover history (2000–2022) and Hansen forest change will be computed for radii of 0.5, 1, 2, 5 and 10 km around it.',
    'change_title': 'Forest change {first}–{last}',
    'change_loss_ha': 'Loss 2001–2025',
    'change_gain_ha': 'Gain 2000–2012',
    'change_net_ha': 'Net 2001–2012',
    'change_gain_undated_note': (
        'Hansen dates loss year by year, but gain is an undated flag covering '
        '2000–2012 only and “has not been updated in subsequent versions”. So gain '
        'is the dashed level inside the shaded window, not a series, and the net is '
        'taken over 2001–2012 — the years both bands share.'
    ),
    'change_forest2000_ha': 'Forest in 2000',
    'change_running': 'Reading Hansen loss and gain…',
    'radius_label': 'Radius',
    'gbif_species_tab': 'Species (GBIF)',
    'gbif_species_tab_hint': (
        'Species already recorded in GBIF inside each buffer around the study '
        'point. It is an aggregate query — it counts the records without '
        'downloading them — and honours the same filters as the sidebar search. The '
        'buffers are cumulative discs: the 10 km one includes everything in the 5 '
        'km one.'
    ),
    'gbif_buffers_note': 'Cumulative discs · queried live from GBIF',
    'gbif_buffers_empty': 'No records at this radius with the current filters.',
    'gbif_col_species': 'Species',
    'gbif_col_records': 'Records',
    'gbif_species_tab_short': 'Species',
    'download_button': 'Download data',
    'export_dialog_title': 'Download data',
    'export_dialog_desc': (
        'An ODS spreadsheet with one tab per table and a metadata tab carrying the '
        'full provenance of every query. Opens in LibreOffice, Excel and Google '
        'Sheets.'
    ),
    'export_point_desc': 'A spreadsheet with: the GLC-FCS30D class of the clicked pixel year by year, one tab per radius ({radii} km) with the full 2000–2022 series, Hansen loss/gain, the class dictionary and a metadata tab.',
    'download_point_button': 'Download point spreadsheet (.ods)',
    'download_point_hint': 'Click a point on the map to enable this.',
    'export_choose_point_first': 'Choose a point on the map first.',
    'export_stage_building': 'Building the spreadsheet',
    'export_sheet_failed': 'Failed to generate the spreadsheet: {exc}',
    'provenance_callout': (
        'No number leaves here without provenance: the metadata tab states which '
        'dataset, which bands, which scale and which reducer produced each table, '
        'and carries the attributions that must be cited.'
    ),
    'no_point_badge': 'no point',
    'gbif_export_ods_hint': (
        'ODS workbook: one metadata tab (point, filters, caveats and licences) and '
        'one tab per radius, listing species and their record counts.'
    ),
    'gbif_export_csv_hint': (
        'Single CSV covering every radius (radius_km, species, records, % of '
        "radius). No metadata — the workbook's caveats still apply."
    ),
    'gbif_export_nothing': 'List the species before exporting.',
    'err_coord_swapped': '{point} is outside the span the world page covers, but {flipped} is inside — latitude and longitude look swapped.',
    'err_coord_outside_world': '{point} is outside the span the world page covers (60°S to 85°N).',
    'err_earth_engine_query': 'Earth Engine query failed: {exc}',
    'err_no_landcover': 'No land-cover data found at this point.',
    'err_forest_failed': 'Failed to read the forest data: {exc}',
    'help_trigger': 'How to use',
    'help_dialog_title': 'How to use Naturametrics World',
    'help_dialog_desc': 'Land-cover history, disturbance and forest change at any point from 60°S to 85°N.',
    'help_step1_title': 'Choose a point',
    'help_step1_body': 'Click anywhere on the map between 60°S and 85°N. A marker is created and five analysis areas (0.5, 1, 2, 5 and 10 km radius) are drawn around it. Clicks made on the Brazil, Canada or USA pages outside their country land here. The page opens on Brazil and Africa; use «Show Asia and Australasia» to load the rest of the land-cover tiles.',
    'help_step2_title': 'Read the land-cover history',
    'help_step2_body': 'The chart below the map shows one column per year, 2000–2022, in the GLC-FCS30D legend colours. Switch the radius across 0.5/1/2/5/10 km and use the «%» switch to toggle between hectares and share of area.',
    'help_step3_title': 'Mind the classes',
    'help_step3_body': 'GLC-FCS30D is a global land-cover map with a fine classification (33 classes), so «Cropland» and «Wetlands» are what the satellite classification sees, not land-use records. It is a global product: less exact locally than a national map. Wetlands and forest are separate classes; the chart does not merge them.',
    'help_step4_title': 'Read the forest change',
    'help_step4_body': (
        'Hansen Global Forest Change gives tree-cover loss year by year, 2001 to '
        '2025, plus an undated gain flag. The «Forest threshold» control sets what '
        'canopy percentage in 2000 counts as forest — raise it to restrict the '
        'count to denser stands.'
    ),
    'help_step5_title': 'Read the disturbance panels',
    'help_step5_body': 'Disturbance history shows tree-cover loss each year (Hansen: the cause is not recorded); time since disturbance counts years since the last detected loss on pixels that were forest in 2000, capped at 2001; Fire shows MODIS burned area by year; Tree canopy shows the canopy trend (2000 canopy minus loss: regrowth is not counted).',
    'help_step6_title': 'Switch the imagery',
    'help_step6_body': 'The GBIF section draws occurrence records from zoom 10 and can filter by name, classification, record type and year. With a study point chosen, «Species in the buffers» lists what has been recorded in each radius.',
    'help_step7_title': 'Download the data',
    'help_step7_body': (
        '«Download data» writes an ODS spreadsheet with every table behind the '
        'charts and a metadata tab explaining how each number was computed.'
    ),
    'help_limitations_title': 'Limitations worth knowing',
    'help_limit_1': 'GLC-FCS30D has one map per year from 2000 to 2022 at 30 m, and the page covers 60°S to 85°N. Open water has no land class.',
    'help_limit_2': 'GLC-FCS30D is a global classification of land cover at 30 m, not a record of land use or ownership, and less exact locally than a national map. Class changes between consecutive years include classification noise.',
    'help_limit_3': (
        'Hansen gain is undated — a single flag for 2000–2012 in the original '
        'product — so it cannot be filtered by year the way loss can. Hansen «loss» '
        'is any canopy loss, including fire and logging, not only clearing.'
    ),
    'help_limit_4': (
        '30 m resolution: a 1 km radius holds about 3,500 pixels, so a few '
        'misclassified pixels already move the percentages.'
    ),
    'cite_trigger': 'How to cite',
    'cite_dialog_title': 'How to cite',
    'cite_dialog_desc': 'If Naturametrics World contributed to your work, cite it and also the datasets used.',
    'cite_sources_title': 'Data sources — cite these too',
    'cite_sources_desc': (
        'Each source has its own attribution requirements. When publishing figures '
        'or numbers obtained here, cite whichever ones were used.'
    ),
    'cite_example_title': 'Example of use in text',
    'cite_example_body': '"The study area was analysed with Naturametrics (Biondo et al., 2026), using GLC-FCS30D (Zhang et al., 2024), NASA NEX-GDDP-CMIP6 (Thrasher et al., 2022) and Hansen Global Forest Change (Hansen et al., 2013)."',
    'app_name': 'Naturametrics World — Land cover, disturbance and forest change',
    'go_to_canada': 'Canada',
    'go_to_usa': 'USA',
    'go_to_world': 'World',
    'start_hint': 'Click anywhere on the map, from 60°S to 85°N, to start',
    'glc_toggle_label': 'GLC-FCS30D land cover',
    'glc_coverage_note': 'GLC-FCS30D is a global land-cover map at 30 m, one map per year from 2000 to 2022. The page opens with the Americas and Europe–Africa; Asia and Australasia load on request.',
    'glc_empty': 'No GLC-FCS30D land cover here (open water, or outside its tiles). The disturbance, fire, canopy and forest-change panels still answer where there is land.',
    'err_extra_failed': 'Earth Engine query failed: {exc}',
    'dist_title': 'Disturbance history',
    'dist_hint': 'Tree-cover loss each year (Hansen Global Forest Change). The product does not record the cause.',
    'dist_empty': 'No change detected in this buffer.',
    'dist_attribution': 'Hansen/UMD/Google/USGS/NASA — Global Forest Change v1.13 · 30 m · 2001–2025',
    'age_title': 'Time since disturbance',
    'age_hint': "Forest area (canopy in 2000) by years since the last detected tree-cover loss. The last bar is censored: not lost since 2001, not 'older than 25 years'.",
    'age_empty': 'No tree cover in this buffer.',
    'age_attribution': 'Derived from Hansen Global Forest Change (lossyear, treecover2000) · 30 m',
    'age_tree_area': 'Tree-covered area',
    'age_tree_share': 'Share of buffer',
    'age_censored_share': 'Not lost since 2001',
    'fire_title': 'Fire (MODIS)',
    'fire_hint': 'Burned area by year from MODIS MCD64A1 (500 m, from 2001). It maps burned area, not severity; small fires fall between pixels.',
    'fire_empty': 'No MODIS-mapped burned area in this buffer.',
    'fire_attribution': 'NASA — MODIS MCD64A1 burned area, v6.1 · 500 m',
    'canopy_title': 'Tree canopy cover',
    'canopy_hint': "Mean tree canopy cover (%) of each buffer, by year: Hansen's 2000 canopy minus the pixels lost by that year (regrowth is not counted).",
    'canopy_attribution': 'Hansen/UMD/Google/USGS/NASA — Global Forest Change (treecover2000, lossyear) · 30 m',
    'help_limit_5': 'Time since disturbance is derived, not measured: it starts the clock at 2001 and cannot say how old a stand that was never lost since then is. MODIS burned area (500 m) misses small fires; Hansen loss does not say the cause.',
    'section_disturbance_layers': 'Disturbance and fire',
    'burn_year_note': 'Year of the most recent burn seen by MODIS, 2001 (pale) to 2025 (dark).',
    'east_toggle': 'Show Asia and Australasia',
    'loss_year_toggle': 'Last tree-cover loss (Hansen)',
    'loss_year_note': 'Year of the most recent tree-cover loss, 2001 (pale yellow) to 2025 (dark red).',
    'burn_year_toggle': 'Last burn (MODIS)',
    'group_study_area': 'Study point',
    'group_landcover': 'Basemap & land cover',
    'group_forest': 'Forest, canopy & disturbance',
    'group_biodiversity': 'Biodiversity (GBIF)',
    'compare_toggle': 'Compare two years',
    'compare_year_left': 'Year on the left (baseline)',
    'compare_note': 'Drag the divider on the map. The right side is the year chosen above; the left side is this year. Defaults: the oldest and the newest year.',
    'extras_running': 'Reading…',
    'err_extra_failed': 'Earth Engine query failed: {exc}',
    'metrics_title': 'Landscape metrics',
    'metrics_hint': 'Patches, largest patch, edge density, effective mesh size and diversity of the natural-vs-other classes in each radius, on the latest land-cover year.',
    'metrics_none': 'No GLC-FCS30D land cover here: no landscape metrics.',
    'biomass_title': 'Above-ground biomass',
    'biomass_hint': "Mean biomass (Mg/ha) by year for the selected radius, with the product's own uncertainty.",
    'biomass_none': 'No biomass data here.',
    'col_radius': 'Radius',
    'col_patches': 'Patches',
    'col_largest': 'Largest %',
    'col_edge': 'Edge m/ha',
    'col_meff': 'Meff (ha)',
    'col_shannon': 'Shannon',
    'col_evenness': 'Evenness',
    'col_year': 'Year',
    'col_mgha': 'Mg/ha',
    'col_sd': '± (product)',
    'biomass_attr': 'ESA CCI Biomass v6.0 — Santoro & Cartus (2025) · 100 m',
    'tab_dist': 'Disturb.',
    'tab_age': 'Dist. time',
    'tab_fire': 'Fire',
    'tab_canopy': 'Canopy',
    'tab_climate': 'Climate',
    'climate_title': 'Climate, fire weather and relief',
    'climate_hint': "Median of nine CMIP6 models for the point's cell, under two emissions scenarios, with the Köppen-Geiger class and the relief around the point.",
    'tab_forest': 'Forest change',
    'tab_metrics': 'Landscape',
    'tab_biomass': 'Biomass',
    'tab_species': 'Species (GBIF)',
    'metrics_attr': 'GLC-FCS30D 2022 · 30 m',
}
