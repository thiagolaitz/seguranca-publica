# Pipeline de Grafos com Make

Fluxo completo para construir grafos baseados em distâncias, varrer thresholds e gerar gráficos/mapas. O diretório foi pensado para ser extraído como repositório independente no futuro.

## Estrutura

```
Make/
├── Makefile                   # Orquestra o pipeline
├── requirements.txt           # Dependências Python
├── scripts/                   # CLIs individuais (ver seção abaixo)
├── data/ (.gitkeep)           # Dataset bruto (Excel/CSV)
├── build/ (.gitkeep)          # Saídas intermediárias (JSON/JSONL)
└── plots/ (.gitkeep)          # Gráficos e mapas finais
```

Dataset esperado: colunas de ID (`NUM_BO` por padrão), `LATITUDE`, `LONGITUDE`. Para Excel é usada a primeira planilha se `SHEET_NAME` não for informado.

## Preparação

1) Crie/ative um ambiente virtual (opcional).  
2) Instale dependências:
```bash
pip install -r requirements.txt
```
3) Já há um dataset padrão em `Make/data/SpDadosCrimianis_2025_campinas.xlsx`; basta rodar `make -C Make`. Para usar outro arquivo, coloque-o em `Make/data/` (ou passe `DATA_FILE=/caminho/para/arquivo.xlsx`).

## Como rodar com Make

| Alvo                 | Descrição                                                                 |
|----------------------|---------------------------------------------------------------------------|
| `make` / `make run`  | Executa `distances -> graph -> analysis -> plots -> heatmap -> communities-map`. |
| `make help`          | Lista rápida de alvos/variáveis.                                          |
| `make distances`     | Lê o dataset e gera `build/distances.jsonl`.                              |
| `make graph`         | Cria grafo para um `THRESHOLD` e salva resumo/plots.                      |
| `make analysis`      | Varre múltiplos thresholds e salva métricas consolidadas.                 |
| `make plots`         | Gera gráficos a partir do JSON de métricas.                               |
| `make heatmap`       | Heatmap direto do dataset bruto (sem usar distâncias).                    |
| `make communities-map` | Detecta comunidades e plota as Top-N no mapa (opcional mapa “safe”).    |
| `make clean`         | Limpa `build/` e `plots/`.                                                |

Variáveis principais (linha de comando):  
`DATA_FILE`, `THRESHOLD`, `THRESHOLDS`, `MIN_THRESHOLD`, `MAX_THRESHOLD`, `STEP`, `ID_COL`, `LAT_COL`, `LON_COL`, `SHEET_NAME`, `MAX_ROWS`, `PROCESSES`.  
Plots/visualização: `GRAPH_DEGREE_PLOT`, `GRAPH_DISTANCE_PLOT`, `ANALYSIS_DEGREE_PLOT`, `ANALYSIS_DISTANCE_PLOT`, `SHOW_PLOTS`, `PLOT_RESULTS_SHOW`, `ANALYSIS_SHOW_PLOTS`.  
Comunidades/heatmap: `HEATMAP_OUTPUT`, `COMMUNITIES_*` (threshold, algoritmo, top-N, k-clique, bridges, geojson, mapa seguro).  
Cache: `FORCE_ALL=1` (ou `FORCE_DISTANCES`, `FORCE_GRAPH`, etc.) força recálculo mesmo se o arquivo existir.

Exemplos rápidos:

```bash
# Pipeline completo (distâncias -> gráficos) com thresholds 0.5 a 5km (dataset padrão em Make/data)
make -C Make MIN_THRESHOLD=0.5 MAX_THRESHOLD=5 STEP=0.5

# Só distâncias (primeira aba do Excel)
make -C Make distances

# Grafo único com plots de distância
make -C Make graph THRESHOLD=0.75 GRAPH_DISTANCE_PLOT=1

# Heatmap direto do dataset
make -C Make heatmap HEATMAP_OUTPUT=plots/campinas_heatmap.html

# Comunidades no mapa (Top 7) + mapa de “safe communities”
make -C Make communities-map \
  COMMUNITIES_THRESHOLD=0.5 COMMUNITIES_TOP_N=7 \
  COMMUNITIES_MAP_OUTPUT=plots/communities_threshold0_5km.html \
  COMMUNITIES_BRIDGES_TOP=10 COMMUNITIES_BRIDGES_SAMPLE=50 \
  COMMUNITIES_NEIGHBORHOODS_GEOJSON=data/Regioes_Campinas_SME.geojson \
  COMMUNITIES_SAFE_TOP=5 COMMUNITIES_SAFE_MIN_SIZE=100 \
  COMMUNITIES_SAFE_OUTPUT=plots/communities_safe.html
```

## Scripts (uso direto, fora do Make)

- `scripts/calculate_distances.py`  
  Converte Excel/CSV em JSONL de distâncias pairwise (Haversine, multiprocessado).  
  Principais flags: `--input`, `--output`, `--id-col`, `--lat-col`, `--lon-col`, `--sheet-name`, `--max-rows`, `--processes`.  
  Exemplo:
  ```bash
  python scripts/calculate_distances.py --input data/SpDadosCrimianis_2025_campinas.xlsx --output build/distances.jsonl --sheet-name Planilha1
  ```

- `scripts/create_graph.py`  
  Lê o JSONL de distâncias, cria um grafo para um threshold e salva estatísticas + plots opcionais.  
  Flags: `--distances`, `--threshold`, `--summary-json`, `--plots-dir`, `--plot-distances`, `--plot-degree-dist`, `--plot-bins`, `--show-plots`.  
  ```bash
  python scripts/create_graph.py --distances build/distances.jsonl --threshold 1.0 --summary-json build/graph_summary_threshold1_00.json --plot-degree-dist
  ```

- `scripts/run_graph_analysis.py`  
  Automação para vários thresholds (chama `create_graph.py` por baixo). Grava progresso incremental em `build/graph_analysis_results.json`.  
  Flags: `--distances`, `--output`, `--create-graph-script`, `--thresholds` ou `--min-threshold/--max-threshold/--step`, `--timeout`, `--plot-degree-dist`, `--plot-distance-dist`, `--show-plots`.  
  ```bash
  python scripts/run_graph_analysis.py --distances build/distances.jsonl --min-threshold 0.5 --max-threshold 3 --step 0.25 --plot-degree-dist
  ```

- `scripts/plot_results.py`  
  Transforma o JSON de análise em gráficos. Se nenhuma flag for passada, gera todos.  
  Flags: `--results`, `--output-dir`, `--average-degree`, `--multi-metrics`, `--connectivity`, `--show`.  
  ```bash
  python scripts/plot_results.py --results build/graph_analysis_results.json --output-dir plots --connectivity
  ```

- `scripts/create_heatmap.py`  
  Heatmap Folium diretamente do dataset (independente do cálculo de distâncias).  
  Flags: `--input`, `--output`, `--lat-col`, `--lon-col`, `--sheet-name`, `--max-rows`, `--radius`, `--blur`, `--max-zoom`, `--zoom-start`, `--tiles`, `--disable-markers`.  
  ```bash
  python scripts/create_heatmap.py --input data/SpDadosCrimianis_2025_campinas.xlsx --output plots/heatmap.html --radius 14 --blur 20
  ```

- `scripts/community_analysis.py`  
  Analisa comunidades para um threshold específico (métricas, top-N, nós ponte, gráfico de tamanhos).  
  Flags: `--distances`, `--threshold`, `--algorithm {greedy,label_prop,asyn_label_prop,kclique}`, `--k-clique`, `--min-size`, `--top-n`, `--bridges-top`, `--bridges-sample`, `--bridges-seed`, `--output-json`, `--plot-path`, `--show-plot`.  
  ```bash
  python scripts/community_analysis.py --distances build/distances.jsonl --threshold 1.0 \
    --algorithm greedy --top-n 10 --bridges-top 15 --output-json build/community_analysis_threshold1_00.json \
    --plot-path plots/community_sizes_threshold1_00.png
  ```

- `scripts/visualize_communities_map.py`  
  Reconstrói o grafo, detecta comunidades e plota em mapa interativo (camadas por comunidade, nós ponte, bordas GeoJSON). Pode gerar mapa das “menores” comunidades (`--safe-*`).  
  Flags: `--distances`, `--threshold`, `--data-file`, `--id-col`, `--lat-col`, `--lon-col`, `--sheet-name`, `--algorithm`, `--k-clique`, `--min-size`, `--top-n`, `--bridges-top`, `--bridges-sample`, `--bridges-seed`, `--neighborhoods-geojson`, `--safe-top`, `--safe-min-size`, `--safe-output`, `--output`, `--zoom-start`, `--tiles`, `--marker-radius`.  
  ```bash
  python scripts/visualize_communities_map.py --distances build/distances.jsonl --threshold 0.5 \
    --data-file data/SpDadosCrimianis_2025_campinas.xlsx --top-n 7 --bridges-top 10 --neighborhoods-geojson data/Regioes_Campinas_SME.geojson \
    --safe-top 5 --safe-min-size 100 --safe-output plots/communities_safe_map.html
  ```

## Saídas

- `build/distances.jsonl`: distâncias entre cada par de pontos.  
- `build/graph_summary_threshold*.json`: estatísticas por threshold.  
- `build/graph_analysis_results.json`: resultados agregados da varredura.  
- `plots/*.png`: gráficos (grau médio, múltiplas métricas, conectividade, etc.).  
- `plots/heatmap.html`: heatmap/markers do dataset bruto.  
- `plots/communities_map.html`: mapa interativo com comunidades e nós ponte (se habilitado).  
- `plots/communities_safe_map.html`: mapa opcional com as menores comunidades (“seguras”).

## Observações rápidas

- `data/` está no `.gitignore`; mantenha somente `data/.gitkeep` versionado.  
- Etapas que já têm saída são puladas; use `FORCE_ALL=1` ou `FORCE_<target>=1` para refazer.  
- Timeouts/erros na análise são registrados no JSON e a varredura segue; ajuste `ANALYSIS_TIMEOUT` se necessário.  
- Todos os scripts rodam em modo batch; use `SHOW_PLOTS=1` ou `--show` apenas se quiser abrir figuras.
