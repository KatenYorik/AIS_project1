# data — общие данные обоих проектов и научной части

Здесь лежит всё, что скрипты читают и пишут: кадры, разметка, собранные датасеты,
веса, метрики. Скриптов в этой папке нет — они разложены по шагам в `project1\`,
`project2\` и `scientific_question\`.

**Как скрипты сюда попадают.** Каждый скрипт, работающий с данными, подключает
`common\aispaths.py` и в самом начале переходит в эту папку. Поэтому пути в
аргументах команд считаются **отсюда**, из какой бы папки ни запускать:

```powershell
cd C:\Users\kkhod\claude\AIS
python project1\step5_metrics\po_klipam.py --weights runs\classify\pretrain_stage2\weights\best.pt --data datasets\birds_v1_course3
```

Абсолютные пути работают как обычно. До 14.09.2026 эти данные лежали в
`razmetka\`, а нынешняя `datasets\` называлась `data\`.

---

## Что здесь лежит

| что | содержимое | откуда | кто читает | размер | пересоздаётся? |
|---|---|---|---|---|---|
| `raw\` | 706 кадров, 9 клипов, 2 кадра/с — первая съёмочная сессия | `extract_frames.py` из `AIS\птицы\` | всё | 142,5 МБ | да, но выбор клипов ручной |
| `raw2\` | 240 кадров, 7 клипов — вторая съёмка | то же | всё | 12,2 МБ | то же |
| **`labels_all.csv`** | **главный файл**: 946 кадров, колонки `label`, `side`, `fixation`, `count`, `count_src` | `merge.py` из выгрузок `labeler.html` | всё | 51 КБ | **нет, ручная разметка** |
| `labels_mine.csv` | выгрузка `labeler.html` по кадрам `raw\` | `labeler.html` | `analyse_new`, `boot`, `dwell`, `group_own`, `make_double` (по умолчанию) | 23 КБ | нет |
| `labels_storona.csv` | ранний проход Кати: сторона головы, 24 кадра | `labeler.html` | `lateral_summary.py`, `labeler.html` | 2 КБ | нет |
| `intervals_snegir2692.csv` | интервальная разметка клипа со снегирём | вручную | `expand_intervals.py` | 1 КБ | нет |
| `scenes_groups.csv` | число птиц и события по сценам | вручную | `group_summary.py` | 1 КБ | нет |
| `kluch.csv` | ключ слепой выборки для повторной разметки — **не открывать до её окончания** | `make_double.py` | `kappa.py` | 3 КБ | да, но тогда выборка другая |
| `dvoinaya\` | 60 кадров со скрытыми именами для повторной разметки | `make_double.py` | человек, потом `kappa.py` | 13,4 МБ | да |
| `sorted_course3\` | 792 кадра по папкам трёх классов | `prepare_data.py` | `dataset.py`, `split_help.py` | 133 МБ | да, `prepare_data.py` |
| `sorted_fine\` | те же 792 кадра по шести мелким классам | `prepare_data.py` | то же | 133 МБ | да |
| `datasets\` | собранные датасеты в формате YOLO-классификации | `prepare_data.py`, `dataset.py`, `wb_stream.py` | `train.py`, `po_klipam.py`, `export_onnx.py` | 1,16 ГБ | да (кроме `pretrain`, см. ниже) |
| `runs\classify\` | веса и журналы ultralytics, 13 запусков | `train.py` | `po_klipam.py`, `export_onnx.py`, узлы ROS | 112 МБ | только переобучением, 13–27 мин на запуск |
| `results\` | метрики 13 запусков (`*.json`) и `onnx_validation.json` | `train.py`, `export_onnx.py` | `svodka.py`, отчёты, контроллер (`confusion`) | 60 КБ | только переобучением |
| `cvat\` | разметка для импорта в CVAT и Roboflow | `to_cvat.py` | CVAT / Roboflow | 288 МБ | да, `to_cvat.py` |
| `B_data.json` | матрицы переходов `B`: своя съёмка и WetlandBirds | `estimate_B.py` | контроллер (`set_B_from_data`) | 1 КБ | да |
| `yolo11n-cls.pt` | исходные веса ImageNet | ultralytics скачивает сам | `train.py` | 5,5 МБ | да, автоматически |

### Датасеты в `datasets\`

Во всех — структура `train\<класс>\*.jpg` и `val\<класс>\*.jpg`, деление по клипам,
кроме `birds_v1_random`.

| датасет | что это | запуск в `runs\` |
|---|---|---|
| `birds_v1_course3` | **основной**: три класса, `seed 5`, 12 клипов / 588 кадров в обучении, 4 / 204 в проверке | `small_*`, `aug_*`, `frozen`, `frozen_augoff`, `pretrain_stage2` |
| `birds_v1_fine` | те же кадры, шесть мелких классов | `base` |
| `birds_v1_random` | те же кадры, деление **по кадрам** — нечестное, для сравнения | `small_100_random` |
| `birds_v1_episode` | деление по эпизодам 10 с с защитной полосой 2 с | `frozen_ep10` |
| `birds_v1_episode_noryab` | то же без клипа с дроздом | — (запуск не делался) |
| `birds_v1_course3_drop` | клип с дроздом убран из обучения, проверка прежняя | `frozen_drop` |
| `birds_v1_fixval` | проверка назначена вручную: снегирь + дрозд + кормушка | `frozen_fixval` |
| `pretrain` | 1947 вырезок Visual WetlandBirds по видам, 13 видов | — |
| `pretrain_split` | те же вырезки, деление по видео: 1567 / 380 | `pretrain_stage1` |
| `clearml` | папки версий датасета v1 и v2 перед заливкой в ClearML | — |

`pretrain` пересоздать можно, но дорого: `wb_stream.py` заново скачивает нужные
видео из архива на 9,4 ГБ.

---

## Соглашения

**Имена кадров не менять.** Из имени восстанавливаются клип и порядок кадров, без
этого невозможны честное деление и марковский анализ:

```
snegir2692_t00135.jpg     своя съёмка: клип, время в десятых долях секунды (13,5 с)
<видео>_f01234.jpg        вырезки WetlandBirds: видео, номер кадра
```

Разбирает имя `parse_frame_name` в `project1\step2_dataset\extract_frames.py`,
регулярка `^(.+)_[tf](\d+)$`.

**Формат `results\<запуск>.json`:** `accuracy`, `macro_f1`, `weighted_f1`, `labels`,
`confusion` (строки — истина, столбцы — ответ), `experiment`, `note`, `fliplr`,
`baseline_class`, `baseline_accuracy`, `strongest_constant_class`,
`strongest_constant_accuracy`.

**Порядок классов у моделей — алфавитный** (так делает ultralytics):
`alert, empty, feeding`.

**Что класть в git.** Да: `labels_all.csv`, `results\*.json`, итоговый
`runs\classify\pretrain_stage2\weights\best.onnx`. Нет: кадры, `datasets\`, `sorted_*`,
`cvat\`, веса `.pt` — это ровно то, о чём лекция 5: датасет версионируется в ClearML,
а не в git.

**Рядом, но не здесь:** исходные видео — `AIS\птицы\`, открытый датасет —
`AIS\wetlandbirds\`.
