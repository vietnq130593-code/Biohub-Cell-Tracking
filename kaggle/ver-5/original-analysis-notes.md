# Ghi chú phân tích gốc — biohub-942proxy-fork-v1 (0.945)

8 cell markdown đầu của notebook `pawanmali/biohub-942proxy-fork-v1`, giữ nguyên văn
(tiếng Nga/Anh) để tra cứu khi tune. Nguồn sự thật cho mọi quyết định tham số.
Notebook đầy đủ: `kaggle/ver-5/original-biohub-942proxy-fork-v1.ipynb`.

---

<!-- ======== markdown cell [0] của notebook gốc ======== -->

## 📖 What is this competition about?

Imagine watching a 3D movie of a zebrafish embryo under a microscope. 
But this isn't ordinary cinema — **each frame is volumetric, not flat**.

Think of it as a layered cake with 64 slices, and hundreds of glowing cells floating in every layer. 
Your job is to trace the fate of **every single cell** from the beginning of the movie to the end.

---

### 🎯 Three main tasks

| Task | What to do | Real-life analogy |
|------|-----------|-------------------|
| 🔍 **Detect** | Find all cells in a frame | Find all glowing marbles in murky jelly |
| 🔗 **Track** | Link cells across frames | Figure out that the marble in frame #5 is the same one from frame #4 |
| 🌳 **Lineage** | Spot division events | Notice when one marble splits into two |

---

### 😤 Why is this hard?

- **Thousands of cells**, all looking identical — like tennis balls in a crowd
- They **move, deform, and divide** during filming
- Images are **noisy** — not all cells are clearly visible, some hide
- Annotations are **sparse** — scientists labeled only a fraction of cells, 
  total count is a mystery (hint: check `estimated_number_of_nodes`)

---

### 📊 How are solutions scored?

The metric has **two components**:

| Component | Weight | What it measures | Plain English |
|-----------|--------|-----------------|---------------|
| **Edge Jaccard** | ~85% | Quality of cell-to-cell links | Did you connect the right cells with arrows? |
| **Division Jaccard** | ~15% | Quality of division detection | Did you find where a mother cell split into two daughters? |

**Final score** = weighted sum of the two Jaccard metrics.

💡 **Gotcha:** Due to the formula, the metric **can exceed 1.0**!

---

### 🧠 Key insight about the metric

> Cell coordinates are compared in **physical space** (microns), 
> not in voxels. Scale: `z=1.625 µm/voxel`, `y=x=0.40625 µm/voxel`.

This means a 1-voxel error in Z ≠ a 1-voxel error in X/Y. 
**XY centroid accuracy is 4× more important** than Z!

---

### 📁 Input data

- **4D video:** shape `(T=100, Z=64, Y=256, X=256)`, `uint16` format
- **Storage format:** Zarr v3 (modern format for large arrays)
- **Dataset size:** 87.61 GB, 199 training videos + hidden test set
- **Train/Test split:** by embryo (one embryo won't appear in both train and test)

---

### 🏆 Output format

A CSV file with a graph of two row types:

| Row | Description | Example |
|-----|-------------|---------|
| **Node** | Cell with ID and coords (t, z, y, x) | `node, 1, 0, 32, 128, 128` |
| **Edge** | Link between cells (source_id → target_id) | `edge, -1, -1, -1, -1, -1, 1, 2` |

Where:
- **Node:** *"Cell #1 at frame 0 is at position (z=32, y=128, x=128)"*
- **Edge:** *"Cell #1 from frame 0 is the same cell as #2 in frame 1"*

---

<!-- ======== markdown cell [1] của notebook gốc ======== -->

# 📈 Experiments & Results — Heuristic Pipeline Evolution

## 🧪 Baseline: DoG + Hungarian Tracker (No ML)

Каждая версия — это улучшение предыдущей. Ниже — что менялось и какой прирост давало.

| Version | LB Score | Δ | Ключевое изменение | Механизм |
|---------|----------|---|-------------------|----------|
| v2 (baseline) | 0.808 | — | DoG detector + Hungarian linker | Стартовая точка |
| v3 | 0.827 | +0.019 | + prune_isolated, rel_threshold 0.02→0.045 | Удаление одиночных узлов, жёстче порог |
| v4 | 0.834 | +0.007 | + short-track filter (min_len=6) | Удаление мусорных треков короче 6 кадров |
| v5 | 0.848 | +0.014 | + two-pass Hungarian, motion prediction | Сначала tight gate (6µm), потом loose (8µm) |
| v6 | 0.858 | +0.010 | xy_downsample 4→2, rel_threshold 0.025 | Точнее детекция, больше клеток |
| v7 | 0.860 | +0.002 | + add_safe_divisions | Попытка найти деления (не сработала) |

---

## 📊 Ключевые метрики по версиям

| Metric | v1 | v2 | v3 | v4 | v5 | v6 |
|--------|----|----|----|----|----|----|
| **LB Score** | 0.808 | 0.827 | 0.834 | 0.848 | 0.858 | **0.860** |
| Edge Jaccard (local) | 0.4495 | 0.4508 | 0.4476 | 0.4612 | 0.4702 | 0.4715 |
| Division Jaccard | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Pred/GT ratio | 72.6x | 70.6x | 68.5x | 70.7x | 70.9x | 70.9x |
| Время на 200 видео | 1.5 ч | 1.7 ч | 1.9 ч | 2.7 ч | 4.2 ч | 5.5 ч |

---

## 💡 Главные выводы

### ✅ Что дало прирост:
1. **Two-pass Hungarian** (+0.014) — самый большой скачок. Разделение на уверенные и спорные связи.
2. **xy_downsample=2** (+0.010) — точность центроидов важнее скорости.
3. **Prune + threshold** (+0.019) — базовые фильтры мусора.

### ❌ Что не сработало:
- **add_safe_divisions** (+0.002) — Division Jaccard остался 0.0000. Нужна ML-модель.

### 🔴 Нерешённые проблемы:
- **Over-prediction: 70x** — детектим все клетки, GT размечено только 6%
- **Division Jaccard = 0** — теряем 15% скора полностью

---

## 🎯 Что дальше?

Эвристики упёрлись в потолок ~0.86. Для роста нужны:
1. **ML-детектор** (UNet / StarDist / Cellpose) — решить over-prediction
2. **Модель делений** — предсказывать митоз по интенсивности и форме
3. **Глобальная оптимизация графа** — вместо жадного связывания

---

<!-- ======== markdown cell [2] của notebook gốc ======== -->

# 📊 Biohub Cell Tracking — Полный Анализ Эволюции Решения

## 🎯 Эксперименты и результаты (v0.923 → v0.934)

### Общая таблица всех версий

| # | Notebook Ver | LB Score | Proxy Score | Adj Edge Jaccard | Division Jaccard | Div TP/FP/FN | Missed GT | Spurious Pred | Fragmented | Ключевое изменение |
|---|-------------|----------|-------------|------------------|------------------|--------------|-----------|---------------|------------|---------------------|
| 1 | v10 | 0.923 | 0.9292 | 0.9167 | 0.1250 | 1/2/2 | 39 | 95670 | 55 | Baseline (dual-seed + harmonic) |
| 2 | v11 | 0.927 | 0.9294 | 0.9152 | 0.1429 | 1/1/3 | 39 | 95605 | 57 | Safe div: 12/15→8/11, parent mid-track |
| 3 | v15 | 0.928 | 0.9315 | 0.9172 | 0.1429 | 1/1/3 | 35 | 93450 | 61 | SEC_DET: 0.475→0.70, GAP_UM: 5.8→6.5 |
| 4 | v16 | 0.930 | 0.9438 | 0.9238 | 0.2000 | 1/0/3 | 36 | 92193 | 55 | BIDIR: 0.30→0.15, DIV_WEIGHT: 1.0→1.2, GAP2+RESCUE on |
| 5 | v17 | 0.931 | 0.9325 | 0.9158 | 0.1667 | 1/1/3 | 35 | 94541 | 60 | SEC_DET: 0.70→0.475 (откат) |
| 6 | v20 | 0.933 | 0.9361 | 0.9194 | 0.1667 | 1/1/3 | 40 | 90993 | 56 | SEC_DET: 0.475→0.80, BIDIR: 0.30→0.15 |
| 7 | v22 | 0.930 | 0.9396 | 0.9229 | 0.1667 | 1/1/3 | 42 | 90482 | 53 | SEC_DET: 0.80→0.85 |
| 8 | v27 | 0.934 | 0.9384 | 0.9218 | 0.1667 | 1/0/3 | 36 | 91455 | 56 | EDGE_WEIGHT: 0.15→0.20, BIDIR: 0.30→0.15, GAP_UM: 6.5→5.8 |

---

## 🔬 Детальный анализ по версиям

### v1 (0.923) — Baseline

**Параметры:**
- SEC_DET = 0.475
- BIDIR = 0.30
- EDGE_WEIGHT = 0.15
- GAP_UM = 5.8
- ILP_DISAPPEAR = 1.5
- ILP_DIVISION = 1.0
- DeepCenter = epoch 2, best.pt

**Метрики:** Proxy 0.9292 | LB 0.923 | Div: 1/2/2

**Итог:** Стартовая точка. Div FP=2 — есть ложные деления.

---

### v2 (0.927) — Ужесточение Safe Divisions

**Изменения:**
- SAFE_DIV_MAX_UM: 12.0 → 8.0
- SAFE_DIV_SISTER_MAX_UM: 15.0 → 11.0
- Добавлено требование: parent mid-track (source in incoming)

**Метрики:** Proxy 0.9294 (+0.0002) | LB 0.927 (+0.004) | Div: 1/1/3

**Анализ:**
- Div FP: 2 → 1 ✅
- Div Jaccard: 0.125 → 0.143 ✅
- LB вырос +0.004 при почти том же proxy

**Вывод:** Ужесточение делений дало чистый LB-рост без proxy-изменений. Значит, на dense LB ложные деления наказываются сильнее, чем на sparse proxy.

---

### v3 (0.928) — Усиление Secondary Detection

**Изменения:**
- SEC_DET: 0.475 → 0.70
- GAP_UM: 5.8 → 6.5
- GAP_CLOSE_MAX_GAP: 2 → 3 (потом откат)

**Метрики:** Proxy 0.9315 (+0.002) | LB 0.928 (+0.001) | Missed GT: 39→35

**Анализ:**
- Missed GT: -4 ✅
- Spurious: -2155 ✅
- Обе метрики улучшились

**Вывод:** SEC_DET=0.70 + GAP_UM=6.5 дали позитивный сдвиг. Это первый признак, что вторичная модель добавляет полезные детекции.

---

### v4 (0.930) — Комбо: BIDIR↓ + DIV_WEIGHT↑ + GAP2/RESCUE

**Изменения:**
- BIDIR: 0.30 → 0.15
- ILP_DIVISION_WEIGHT: 1.0 → 1.2
- ILP_DISAPPEARANCE_WEIGHT: 1.5 → 2.0
- GAP2_RECOVERY: включён
- SHORT_TRACK_RESCUE: включён
- DeepCenter: epoch 2 → 500 (checkpoint_last.pt)

**Метрики:** Proxy 0.9438 (+0.012!) | LB 0.930 (-0.002) | Div: 1/0/3 | Fragmented: 61→55

**Анализ:**
- Div FP: 1 → 0 ✅
- Fragmented: -6 ✅
- Spurious: -1257 ✅
- НО LB УПАЛ!

**Вывод:** 🔴 КЛЮЧЕВОЙ МОМЕНТ! Proxy вырос на +0.012, но LB упал на -0.002. Это первый случай расхождения. Причина: BIDIR=0.15 слабее, чем 0.30 — меньше bidirectional-консенсуса. На sparse proxy это не видно, но на dense LB связи стали хуже.

---

### v5 (0.931) — Откат SEC_DET

**Изменения:**
- SEC_DET: 0.70 → 0.475 (вернули)

**Метрики:** Proxy 0.9325 (-0.011) | LB 0.931 (+0.001) | Missed GT: 36→35

**Анализ:**
- Proxy УПАЛ на -0.011
- LB ВЫРОС на +0.001
- Spurious: +2348 (хуже для proxy)

**Вывод:** 🔴 Обратный паттерн! Уменьшение SEC_DET ухудшило proxy, но улучшило LB. Подтверждение: SEC_DET=0.475 лучше для LB, чем 0.70, несмотря на худший proxy.

---

### v6 (0.933) — Оптимум: SEC_DET=0.80 + BIDIR=0.30

**Изменения:**
- SEC_DET: 0.475 → 0.80
- BIDIR: 0.15 → 0.30
- GAP_UM: 6.5 (оставлен)

**Метрики:** Proxy 0.9361 (+0.004) | LB 0.933 (+0.002) | Spurious: 94541→90993

**Анализ:**
- Spurious: -3548 ✅
- Missed GT: 35→40 (хуже)
- Обе метрики выросли

**Вывод:** ✅ ОПТИМУМ НАЙДЕН! SEC_DET=0.80 + BIDIR=0.30 дали синхронный рост. В связке эти параметры работают лучше, чем по отдельности.

---

### v7 (0.930) — Перебор SEC_DET=0.85

**Изменения:**
- SEC_DET: 0.80 → 0.85

**Метрики:** Proxy 0.9396 (+0.004) | LB 0.930 (-0.003) | Missed GT: 40→42

**Анализ:**
- Proxy вырос, LB упал
- Missed GT: +2 (пропустили реальные клетки)
- Fragmented: 56→53 (улучшилось)

**Вывод:** 🔴 SEC_DET=0.85 слишком много. Модель стала увереннее, но пропускает реальные клетки (missed +2). На dense LB это критично.

---

### v8 (0.934) — Финальный баланс

**Изменения:**
- EDGE_WEIGHT: 0.15 → 0.20
- BIDIR: 0.30 → 0.15
- GAP_UM: 6.5 → 5.8
- SEC_DET: 0.80 (оставлен)

**Метрики:** Proxy 0.9384 (-0.001) | LB 0.934 (+0.001) | Div: 1/0/3 | Missed GT: 42→36

**Анализ:**
- Missed GT: -6 ✅
- Div FP: 1 → 0 ✅
- Spurious: +973 (чуть хуже)
- LB вырос до 0.934

**Вывод:** ✅ Финальный баланс сработал. BIDIR=0.15 + EDGE_WEIGHT=0.20 + GAP_UM=5.8 дали лучший LB, хотя proxy чуть ниже пика (0.9396 → 0.9384).

---

## 📈 Ключевые паттерны и выводы

### 1. Proxy НЕ коррелирует с LB на 100%

| Направление | Случаи | Пример |
|-------------|--------|--------|
| Proxy↑, LB↑ | v3, v6 | SEC_DET 0.70, затем 0.80+BIDIR 0.30 |
| Proxy↑, LB↓ | v4, v7 | BIDIR↓, SEC_DET 0.85 |
| Proxy↓, LB↑ | v5, v8 | SEC_DET откат, финальный баланс |

### 2. Критические параметры (матрица влияния)

| Параметр | Оптимум | Влияние на LB | Влияние на Proxy |
|----------|---------|---------------|------------------|
| SEC_DET | 0.80 | +0.002 (0.475→0.80) | -0.004 (0.475→0.80) |
| BIDIR | 0.30 с SEC_DET=0.80 | +0.002 | +0.004 |
| BIDIR | 0.15 с EDGE=0.20 | +0.001 | -0.001 |
| EDGE_WEIGHT | 0.20 | +0.001 | -0.001 |
| GAP_UM | 5.8 (финал) | +0.001 | -0.001 |
| SAFE_DIV | 7/12 (ужесточённые) | +0.004 | +0.000 |

### 3. Матрица взаимосвязей
SEC_DET × BIDIR:
0.475 + 0.30 = LB 0.923 (baseline)
0.70 + 0.30 = LB 0.928 (+0.005)
0.70 + 0.15 = LB 0.930 (+0.002, но proxy↑↑)
0.80 + 0.30 = LB 0.933 (+0.003) ← ОПТИМУМ
0.85 + 0.30 = LB 0.930 (-0.003) ← перебор
0.80 + 0.15 + EDGE 0.20 = LB 0.934 (+0.001) ← финал


### 4. Division Jaccard — стабильно низкий

- Все версии: 0.125-0.200
- Только 1 TP из 3 GT делений в валидации
- Div FP удалось довести до 0 (v4, v8)
- Division Jaccard = 15% от LB, но мы застряли на 0.167

### 5. Главные метрики для отслеживания

| Метрика | Что показывает | Оптимум в наших версиях |
|---------|----------------|-------------------------|
| Missed GT Nodes | Пропущенные реальные клетки | 35-36 (v3, v5, v8) |
| Spurious Pred Nodes | Ложные детекции | 90-92K (v4, v6) |
| Div FP | Ложные деления | 0 (v4, v8) |
| Fragmented Edges | Разорванные треки | 53-56 (v4, v7, v8) |
| Wrong Association | Неверные связи | 0 (все версии!) |

---

## 🎯 Куда двигаться дальше

1. **Division Jaccard = 0.167** — главный резерв (+15% LB). Нужна отдельная модель для делений.

2. **Missed GT Nodes** — 35-42 пропущенных клеток. Улучшить детекцию слабых/перекрытых клеток.

3. **SEC_DET = 0.80** — оптимум найден, не трогать.

4. **BIDIR** — зависит от контекста:
   - 0.30 при EDGE_WEIGHT=0.15
   - 0.15 при EDGE_WEIGHT=0.20

5. **Wrong Association = 0** — трекинг идеальный, проблема только в детекции и делениях.

---

<!-- ======== markdown cell [3] của notebook gốc ======== -->

## 🔬 Biohub Cell Tracking — Прорыв в Division Geometry: от 0.934 к 0.942

### 📚 Источники анализа

В основе этого эксперимента — три публичные работы, которые мы разобрали по ячейкам:

| # | Работа | LB | Ключевая идея |
|---|--------|-----|---------------|
| 1 | [biohub-div45-stack](https://www.kaggle.com/code/rishabhr0y/biohub-div45-stack) | 0.938 | Расширение геометрии safe divisions + SYMMETRY_TAU |
| 2 | [biohub-cell-tracking](https://www.kaggle.com/code/kunaldesale2408/biohub-cell-tracking) | 0.940 | Тюнинг детекции + ILP division weight |
| 3 | [biohub-lb-942](https://www.kaggle.com/code/analyticaobscura/biohub-lb-942) | 0.942 | Post-process sweep + расширенный валидатор |

---

### 🎯 Что мы поняли из каждой работы

#### 📄 Работа 1 (0.938): Division Geometry Overhaul

**Главный инсайт:** Наши пороги SAFE_DIV_MAX_UM=7 и SISTER_MAX=12 режут реальные деления.

**GT-анализ из их замеров:**
- Sister separation: median **10.4µm**, p90 **13.0µm**, max **13.7µm** → порог 12µm терял **~29% реальных делений**
- Parent-daughter links: max **10.4µm** → порог 7µm терял **~25% реальных делений**

**Что взяли оттуда:**
- Расширили геометрию: `SAFE_DIV_MAX_UM 7→9`, `SAFE_DIV_SISTER_MAX 12→14`
- Добавили новый фильтр `SYMMETRY_TAU = 0.6` — отсекает асимметричные ложные пары
- Перешли на DeepCenter epoch 2 (best.pt)

---

#### 📄 Работа 2 (0.940): Division Geometry + Detection

**Главный инсайт:** Можно улучшить и детекцию, и деления одновременно.

**Что попробовали оттуда:**
- `DET_THRESHOLD 0.965→0.960` — ловить слабые клетки
- `ILP_DIVISION_WEIGHT 1.2→1.3` — пусть ILP сам ищет деления
- `MIN_TRACK_LEN 6→5` — сохранять короткие пост-дивизионные треки
- `DIVERGE_UM 3.5` — золотая середина между 2.25 и 4.5

**Вывод:** Часть изменений сработала, но не все. ILP_DIV 1.3 и DET 0.960 дали нестабильный результат.

---

#### 📄 Работа 3 (0.942): Структурный подход

**Главный инсайт:** Это **не просто параметры** — это другой подход:
- **Post-process sweep** — перебор 7 параметров на кэшированных графах
- **VALIDATOR_N = 8** — расширенная валидация
- **Кэширование инференса** — один прогон модели, много тестов постобработки
- **DeepCenter SAFE_DIV_THRESHOLD 0.12→0.25** — ослабленный veto пропускает больше делений

**Их результат:** Div TP **4** (у нас был 1), Div Jaccard **0.3077** (у нас 0.1667)

---

### 🧪 Что мы применили в нашей v28

Мы **НЕ копировали** сложный пайплайн со свипом. Мы взяли **только проверенные параметры** из работы 0.938 и применили их к нашей обычной архитектуре:

| Параметр | Наша 0.934 | Наша v28 (0.942) | Источник |
|----------|-----------|------------------|----------|
| SAFE_DIV_MAX_UM | 7.0 | **9.0** | Работа 1 |
| SAFE_DIV_SISTER_MAX | 12.0 | **14.0** | Работа 1 |
| SYMMETRY_TAU | 0 (нет) | **0.6** | Работа 1 |
| DeepCenter epoch | 500 | **2 (best.pt)** | Работа 1 |
| EDGE_WEIGHT | 0.15 | **0.20** | Наш 0.934 |
| BIDIR | 0.15 | **0.15** | Без изменений |
| SEC_DET | 0.80 | **0.80** | Без изменений |
| DIVERGE_UM | 2.25 | **2.25** | НЕ меняли! |

**Дополнительно:**
- Добавлен `BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU` в **Configuration Guard** — новый параметр теперь проверяется на дрифт
- `SAFE_DIV_VETO` выключен (`safe_div_add_gate: false`) — DeepCenter не фильтрует safe divisions, полагаемся на SYMMETRY_TAU + divergence

---

### 🏆 Результат

| Метрика | Наша 0.934 | Наша v28 |
|---------|-----------|----------|
| **LB Score** | 0.934 | **0.942** |
| Div TP | 1 | **4** |
| Div Jaccard | 0.1667 | **0.2000** |
| Adj Edge | 0.9218 | **0.9217** |
| Proxy | 0.9384 | **0.9417** |
| Время работы | ~35 мин | ~35 мин |

---

### 💡 Ключевые уроки

1. **Прорыв был в геометрии делений, а не в энсамбле** — мы крутили SEC_DET/BIDIR/EDGE_WEIGHT, а надо было расширять SAFE_DIV пороги и добавлять SYMMETRY_TAU.

2. **Биология важнее параметров** — GT-анализ показал реальные расстояния делений, и мы перестали их резать.

3. **Не всё из 0.940 нужно** — DET 0.960 и ILP_DIV 1.3 ухудшали стабильность, мы их отбросили.

4. **Сложный пайплайн не обязателен** — мы обогнали 0.942 (их LB) простыми точечными правками, без свипа и кэширования.

5. **SYMMETRY_TAU — новый механизм** — его не было в наших работах вообще. Он отсекает ложные широкие пары, которые пропускали старые фильтры.

---

<!-- ======== markdown cell [4] của notebook gốc ======== -->

## 🔬 Biohub Cell Tracking — v29: Edge Feature TTA + Motion Relink Tuning

### 📚 Источники анализа

На основе двух публичных работ, которые мы разобрали по ячейкам:

| # | Работа | LB | Ключевая идея |
|---|--------|-----|---------------|
| 1 | [biohub-run79](https://www.kaggle.com/code/rogerrogerroger3r/biohub-run79?scriptVersionId=347936310) | 0.944 | EDGE_FEATURE_TTA + DEEPCENTER_SAFE_DIV_THRESHOLD 0.26 |
| 2 | [biohub-942tta](https://www.kaggle.com/code/redoctopusk/biohub-942tta) | 0.946 | TTA + PPSWEEP → MOTION_RELINK_TIGHT_UM 5.5 |

---

### 🧠 Что мы поняли из каждой работы

#### 📄 Работа 1 (0.944): Edge Feature TTA

**Главный инсайт:** Мы аугментируем детекцию (8 views), но edge-модель получает признаки только с одного прохода. А ведь симметрии изображения применимы и к связям между клетками.

**Что делает EDGE_FEATURE_TTA:**
- При детекционном TTA модель уже кодирует 8 augmented views
- Раньше feature maps от этих views просто выбрасывались
- Теперь они усредняются и используются для edge scoring

**Эффект:**
- Edge features становятся устойчивее к ориентации
- Edge Jaccard на 44b6_12dfb391: 0.9115 → 0.9256 (+0.014)
- Больше nodes/edges: 42700 → 45004 на том же видео

**Дополнительно:** DEEPCENTER_SAFE_DIV_THRESHOLD поднят до 0.26 — ослабленный veto пропускает больше делений.

---

#### 📄 Работа 2 (0.946): Motion Relink Tightening

**Главный инсайт:** TTA дал больше кандидатов, но среди них стало больше ложных связей. Нужно ужесточить первый проход motion relink.

**Что делает PPSWEEP:**
- Кэширует графы после инференса
- Перебирает 7 постобработочных параметров за 4-5 минут каждый
- Выбирает лучший по proxy score

**Результат свипа:**
- Единственный кандидат, прошедший отбор: `MOTION_RELINK_TIGHT_UM 6.0 → 5.5`
- Proxy: 0.9492 → 0.9512 (+0.0021)
- Adjusted Edge: 0.9261 → 0.9282 (+0.0021)
- Div Jaccard: стабильно 0.2308

**Почему tight=5.5 работает:** TTA даёт больше edge candidates. Tight gate 6.0 пропускал часть ложных связей в плотных областях. Ужесточение до 5.5 отсекает их без потери реальных.

---

### 🧪 Что мы применяем в v29

Мы **НЕ копируем** PPSWEEP и расширенный валидатор — это утяжелит пайплайн с 35 до 80 минут. Мы берём только проверенные улучшения:

| Параметр | Наша v28 (0.942) | v29 (цель 0.944-0.946) | Источник |
|----------|------------------|------------------------|----------|
| EDGE_FEATURE_TTA | ❌ нет | ✅ **включён** | Работа 1 |
| DEEPCENTER_SAFE_DIV_THRESHOLD | 0.25 | **0.26** | Работа 1 |
| MOTION_RELINK_TIGHT_UM | 6.0 | **5.5** | Работа 2 |
| SAFE_DIV_MAX_UM | 9.0 | 9.0 | Без изменений |
| SAFE_DIV_SISTER_MAX | 14.0 | 14.0 | Без изменений |
| SYMMETRY_TAU | 0.6 | 0.6 | Без изменений |
| DIVERGE_UM | 2.25 | 2.25 | Без изменений |
| VALIDATOR_N | 4 | 4 | НЕ трогаем! |
| PPSWEEP | ❌ нет | ❌ нет | НЕ копируем! |

---

### 🏆 Ожидаемый результат

| Метрика | v28 (0.942) | v29 (цель) |
|---------|-------------|------------|
| **LB Score** | 0.942 | **0.944-0.946** |
| Edge Jaccard (44b6_12dfb391) | 0.9115 | 0.9256+ |
| Div Jaccard | 0.2000 | 0.2308 |
| Adj Edge | 0.9217 | 0.9282+ |
| Время работы | ~35 мин | ~35 мин |

---

<!-- ======== markdown cell [5] của notebook gốc ======== -->

### 📚 Источники и улучшения v30

**Источник:** [biohub-lf-dctta](https://www.kaggle.com/code/sjlee101/biohub-lf-dctta) — работа с применением DeepCenter TTA.

**Наши улучшения в v30 (поверх v29 / 0.945):**

| # | Улучшение | Механизм | Ожидаемый эффект |
|---|-----------|----------|------------------|
| 1 | **TTA-fusion для link logits** | Усреднение raw link logits трансформера по всем 8 TTA-видам (а не только по оригиналу) | Основной прирост, +0.002–0.003 |
| 2 | **Secondary Edge Feature TTA** | Усреднение feature maps secondary модели по 8 видам с весом 0.75 | +0.001–0.002 |
| 3 | **DeepCenter TTA** | Аугментация логитов veto-модели DeepCenter по 8 видам | +0.001–0.002 |
| 4 | **MOTION_RELINK_TIGHT_UM = 5.5** | Ужесточение tight gate в motion relink | +0.0021 proxy (подтверждено свипом) |

**Итог:** v30 нацелена на **0.948+** при сохранении времени счёта ~35–40 минут (без PPSWEEP и расширенного валидатора).

---

<!-- ======== markdown cell [6] của notebook gốc ======== -->

# 🧬 Biohub Cell Tracking — Dual-Seed + Harmonic Bidirectional Fusion

Детально разобранная копия одной из лучших публичных работ этого соревнования.

**Leaderboard Score: 0.923**

Ноутбук состоит из пронумерованных ячеек.  
Каждая ячейка подробно описана: что она делает, зачем нужна и на что влияет.

Основные компоненты пайплайна:

- **TemporalUNet3D** — детектор клеток в 3D+время
- **Node Transformer** — оценка связей между клетками соседних кадров
- **ILP-солвер** — глобальное построение графа родословной
- **DeepCenter** — независимая проверка сомнительных восстановленных узлов
- **Ансамбль двух моделей** — primary + secondary с разными random seed
- **Harmonic bidirectional fusion** — связь подтверждается и в прямом, и в обратном направлении

---

<!-- ======== markdown cell [7] của notebook gốc ======== -->

## 1. Глобальная конфигурация пайплайна

