.DEFAULT_GOAL := run

PYTHON ?= python3
DATA_FILE ?= data/SpDadosCrimianis_2025_campinas.xlsx
BUILD_DIR ?= build
PLOTS_DIR ?= plots
DISTANCES_FILE ?= $(BUILD_DIR)/distances.jsonl
RESULTS_FILE ?= $(BUILD_DIR)/graph_analysis_results.json
THRESHOLD ?= 0.5
GRAPH_SUMMARY ?= $(BUILD_DIR)/graph_summary_threshold$(THRESHOLD).json
HEATMAP_OUTPUT ?= $(PLOTS_DIR)/heatmap.html
COMMUNITIES_MAP_OUTPUT ?= $(PLOTS_DIR)/communities_map.html
COMMUNITIES_THRESHOLD ?= $(THRESHOLD)
COMMUNITIES_ALGO ?= greedy
COMMUNITIES_TOP_N ?= 7
COMMUNITIES_MIN_SIZE ?= 3
COMMUNITIES_MARKER_RADIUS ?= 6
COMMUNITIES_ZOOM_START ?= 12
COMMUNITIES_TILES ?= CartoDB positron
COMMUNITIES_K_CLIQUE ?=
COMMUNITIES_BRIDGES_TOP ?= 10
COMMUNITIES_BRIDGES_SAMPLE ?= 50
COMMUNITIES_BRIDGES_SEED ?=
COMMUNITIES_NEIGHBORHOODS_GEOJSON ?= data/Regioes_Campinas_SME.geojson
COMMUNITIES_SAFE_TOP ?= 5
COMMUNITIES_SAFE_MIN_SIZE ?= 100
COMMUNITIES_SAFE_OUTPUT ?= $(PLOTS_DIR)/communities_safe_map.html
MIN_THRESHOLD ?= 0.5
MAX_THRESHOLD ?= 5.0
STEP ?= 0.5
THRESHOLDS ?=
ID_COL ?= NUM_BO
LAT_COL ?= LATITUDE
LON_COL ?= LONGITUDE
SHEET_NAME ?=
MAX_ROWS ?=
PROCESSES ?=
GRAPH_DEGREE_PLOT ?= 1
GRAPH_DISTANCE_PLOT ?= 0
ANALYSIS_DEGREE_PLOT ?= 0
ANALYSIS_DISTANCE_PLOT ?= 0
SHOW_PLOTS ?= 0
PLOT_RESULTS_SHOW ?= 0
ANALYSIS_SHOW_PLOTS ?= 0
ANALYSIS_TIMEOUT ?= 600
FORCE_ALL ?= 0
FORCE_DISTANCES ?= $(FORCE_ALL)
FORCE_GRAPH ?= $(FORCE_ALL)
FORCE_ANALYSIS ?= $(FORCE_ALL)
FORCE_PLOTS ?= $(FORCE_ALL)
FORCE_HEATMAP ?= $(FORCE_ALL)
FORCE_COMMUNITIES_MAP ?= $(FORCE_ALL)

define as_bool
$(if $(filter yes true on 1,$(strip $(1))),1,0)
endef

SHEET_ARG := $(if $(strip $(SHEET_NAME)),--sheet-name "$(SHEET_NAME)",)
MAX_ROWS_ARG := $(if $(strip $(MAX_ROWS)),--max-rows $(MAX_ROWS),)
PROCESSES_ARG := $(if $(strip $(PROCESSES)),--processes $(PROCESSES),)
THRESHOLD_ARGS := $(if $(strip $(THRESHOLDS)),--thresholds "$(THRESHOLDS)",--min-threshold $(MIN_THRESHOLD) --max-threshold $(MAX_THRESHOLD) --step $(STEP))
GRAPH_DEGREE_FLAG := $(if $(call as_bool,$(GRAPH_DEGREE_PLOT)),--plot-degree-dist,)
GRAPH_DISTANCE_FLAG := $(if $(call as_bool,$(GRAPH_DISTANCE_PLOT)),--plot-distances,)
ANALYSIS_DEGREE_FLAG := $(if $(call as_bool,$(ANALYSIS_DEGREE_PLOT)),--plot-degree-dist,)
ANALYSIS_DISTANCE_FLAG := $(if $(call as_bool,$(ANALYSIS_DISTANCE_PLOT)),--plot-distance-dist,)
SHOW_PLOTS_FLAG := $(if $(call as_bool,$(SHOW_PLOTS)),--show-plots,)
PLOT_RESULTS_SHOW_FLAG := $(if $(call as_bool,$(PLOT_RESULTS_SHOW)),--show,)
ANALYSIS_SHOW_FLAG := $(if $(call as_bool,$(ANALYSIS_SHOW_PLOTS)),--show-plots,)
COMMUNITIES_K_CLIQUE_ARG := $(if $(strip $(COMMUNITIES_K_CLIQUE)),--k-clique $(COMMUNITIES_K_CLIQUE),)
PLOTS_MULTI_FILE ?= $(PLOTS_DIR)/plot_multiple_metrics.png

.PHONY: help dirs distances graph analysis plots heatmap communities-map all clean run

help:
	@echo "Targets disponíveis:"
	@echo "  make distances   -> Calcula distâncias JSONL"
	@echo "  make graph       -> Cria um grafo único e gera estatísticas"
	@echo "  make analysis    -> Varre thresholds e salva métricas"
	@echo "  make plots       -> Converte os resultados em gráficos"
	@echo "  make heatmap     -> Gera o mapa/heatmap interativo a partir do dataset bruto"
	@echo "  make communities-map -> Plota as comunidades detectadas no mapa"
	@echo "Variáveis úteis:"
	@echo "  DATA_FILE=... THRESHOLD=... THRESHOLDS=\"0.5,1.0,1.5\" etc."

dirs:
	@mkdir -p $(BUILD_DIR) $(PLOTS_DIR) data

distances: dirs
	@test -f $(DATA_FILE) || (echo "DATA_FILE não encontrado: $(DATA_FILE)" && exit 1)
	@if [ "$(FORCE_DISTANCES)" = "1" ] || [ ! -f "$(DISTANCES_FILE)" ]; then \
		echo ">> Calculando distâncias em $(DISTANCES_FILE)"; \
		$(PYTHON) scripts/calculate_distances.py \
			--input "$(DATA_FILE)" \
			--output "$(DISTANCES_FILE)" \
			--id-col $(ID_COL) \
			--lat-col $(LAT_COL) \
			--lon-col $(LON_COL) \
			$(SHEET_ARG) \
			$(MAX_ROWS_ARG) \
			$(PROCESSES_ARG); \
	else \
		echo ">> distances: $(DISTANCES_FILE) já existe, pulando (use FORCE_DISTANCES=1 para refazer)"; \
	fi

graph: dirs
	@test -f $(DISTANCES_FILE) || (echo "Distâncias não encontradas em $(DISTANCES_FILE). Rode 'make distances'." && exit 1)
	@if [ "$(FORCE_GRAPH)" = "1" ] || [ ! -f "$(GRAPH_SUMMARY)" ]; then \
		echo ">> Construindo grafo (threshold $(THRESHOLD))"; \
		$(PYTHON) scripts/create_graph.py \
			--distances "$(DISTANCES_FILE)" \
			--threshold $(THRESHOLD) \
			--plots-dir "$(PLOTS_DIR)" \
			--summary-json "$(GRAPH_SUMMARY)" \
			$(GRAPH_DEGREE_FLAG) \
			$(GRAPH_DISTANCE_FLAG) \
			$(SHOW_PLOTS_FLAG); \
	else \
		echo ">> graph: $(GRAPH_SUMMARY) já existe, pulando (use FORCE_GRAPH=1 para refazer)"; \
	fi

analysis: dirs
	@test -f $(DISTANCES_FILE) || (echo "Distâncias não encontradas em $(DISTANCES_FILE). Rode 'make distances'." && exit 1)
	@if [ "$(FORCE_ANALYSIS)" = "1" ] || [ ! -f "$(RESULTS_FILE)" ]; then \
		echo ">> Executando análise multi-threshold (saída: $(RESULTS_FILE))"; \
		$(PYTHON) scripts/run_graph_analysis.py \
			--distances "$(DISTANCES_FILE)" \
			--output "$(RESULTS_FILE)" \
			--create-graph-script "scripts/create_graph.py" \
			--plots-dir "$(PLOTS_DIR)" \
			--timeout $(ANALYSIS_TIMEOUT) \
			$(THRESHOLD_ARGS) \
			$(ANALYSIS_DEGREE_FLAG) \
			$(ANALYSIS_DISTANCE_FLAG) \
			$(ANALYSIS_SHOW_FLAG); \
	else \
		echo ">> analysis: $(RESULTS_FILE) já existe, pulando (use FORCE_ANALYSIS=1 para refazer)"; \
	fi

plots: analysis
	@if [ "$(FORCE_PLOTS)" = "1" ] || [ ! -f "$(PLOTS_MULTI_FILE)" ]; then \
		echo ">> Gerando gráficos em $(PLOTS_DIR)"; \
		$(PYTHON) scripts/plot_results.py \
			--results "$(RESULTS_FILE)" \
			--output-dir "$(PLOTS_DIR)" \
			$(PLOT_RESULTS_SHOW_FLAG); \
	else \
		echo ">> plots: artefatos já existem em $(PLOTS_DIR), pulando (use FORCE_PLOTS=1 para refazer)"; \
	fi

heatmap: dirs
	@test -f $(DATA_FILE) || (echo "DATA_FILE não encontrado: $(DATA_FILE)" && exit 1)
	@if [ "$(FORCE_HEATMAP)" = "1" ] || [ ! -f "$(HEATMAP_OUTPUT)" ]; then \
		echo ">> Gerando heatmap em $(HEATMAP_OUTPUT)"; \
		$(PYTHON) scripts/create_heatmap.py \
			--input "$(DATA_FILE)" \
			--output "$(HEATMAP_OUTPUT)" \
			--lat-col $(LAT_COL) \
			--lon-col $(LON_COL) \
			$(SHEET_ARG) \
			$(MAX_ROWS_ARG); \
	else \
		echo ">> heatmap: $(HEATMAP_OUTPUT) já existe, pulando (use FORCE_HEATMAP=1 para refazer)"; \
	fi

communities-map: dirs
	@test -f $(DISTANCES_FILE) || (echo "Distâncias não encontradas em $(DISTANCES_FILE). Rode 'make distances'." && exit 1)
	@test -f $(DATA_FILE) || (echo "DATA_FILE não encontrado: $(DATA_FILE)" && exit 1)
	@if [ "$(FORCE_COMMUNITIES_MAP)" = "1" ] || [ ! -f "$(COMMUNITIES_MAP_OUTPUT)" ]; then \
		echo ">> Gerando mapa de comunidades em $(COMMUNITIES_MAP_OUTPUT)"; \
		$(PYTHON) scripts/visualize_communities_map.py \
			--distances "$(DISTANCES_FILE)" \
			--threshold $(COMMUNITIES_THRESHOLD) \
			--data-file "$(DATA_FILE)" \
			--output "$(COMMUNITIES_MAP_OUTPUT)" \
			--id-col $(ID_COL) \
			--lat-col $(LAT_COL) \
			--lon-col $(LON_COL) \
			--algorithm $(COMMUNITIES_ALGO) \
			--top-n $(COMMUNITIES_TOP_N) \
			--min-size $(COMMUNITIES_MIN_SIZE) \
			--marker-radius $(COMMUNITIES_MARKER_RADIUS) \
			--zoom-start $(COMMUNITIES_ZOOM_START) \
			--tiles "$(COMMUNITIES_TILES)" \
			--bridges-top $(COMMUNITIES_BRIDGES_TOP) \
			--bridges-sample $(COMMUNITIES_BRIDGES_SAMPLE) \
			$(if $(strip $(COMMUNITIES_BRIDGES_SEED)),--bridges-seed $(COMMUNITIES_BRIDGES_SEED),) \
			$(if $(strip $(COMMUNITIES_NEIGHBORHOODS_GEOJSON)),--neighborhoods-geojson "$(COMMUNITIES_NEIGHBORHOODS_GEOJSON)",) \
			$(if $(filter-out 0,$(COMMUNITIES_SAFE_TOP)),--safe-top $(COMMUNITIES_SAFE_TOP),) \
			$(if $(filter-out 0,$(COMMUNITIES_SAFE_TOP)),--safe-min-size $(COMMUNITIES_SAFE_MIN_SIZE),) \
			$(if $(filter-out 0,$(COMMUNITIES_SAFE_TOP)),--safe-output "$(COMMUNITIES_SAFE_OUTPUT)",) \
			$(COMMUNITIES_K_CLIQUE_ARG) \
			$(SHEET_ARG) \
			$(MAX_ROWS_ARG); \
	else \
		echo ">> communities-map: $(COMMUNITIES_MAP_OUTPUT) já existe, pulando (use FORCE_COMMUNITIES_MAP=1 para refazer)"; \
	fi

run:
	$(MAKE) distances
	$(MAKE) graph
	$(MAKE) analysis
	$(MAKE) plots
	$(MAKE) heatmap
	$(MAKE) communities-map

all: run

clean:
	rm -rf $(BUILD_DIR) $(PLOTS_DIR)
	mkdir -p $(BUILD_DIR) $(PLOTS_DIR)
	touch $(BUILD_DIR)/.gitkeep $(PLOTS_DIR)/.gitkeep
