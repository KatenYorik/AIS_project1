# Шаг 6. Эксперименты и улучшения

**Задание.** Не меньше **трёх** экспериментов, направленных на улучшение модели. Каждый
в ClearML и воспроизводим.

Во всех трёх обязательных экспериментах меняется **одна** вещь. Проверка одна и та же:
4 клипа, 204 кадра, константа 0.422 / 0.198. Скрипты — `step4_baseline_model\train.py`
(обучение) и `step2_dataset\prepare_data.py` (датасеты). Здесь лежат только очереди
запусков.

## Эксперимент 1 — объём обучающей выборки

| запуск | обучающих кадров | accuracy | macro-F1 |
|---|---|---|---|
| `small_33` | ~194 (33 %) | 0.426 | 0.329 |
| `small_100` | 588 (100 %) | 0.358 | 0.305 |

Рост объёма **не** помог. На трети данных модель вырождается (`feeding` F1 = 0), на всей
учит все три класса, но обобщает не лучше. Ограничение — не число кадров.

## Эксперимент 2 — аугментация

| аугментация | accuracy | macro-F1 |
|---|---|---|
| выключена (`aug_off`) | **0.387** | **0.345** |
| обычная (`small_100`): поворот ±5°, сдвиг 5 %, масштаб 20 %, яркость 0.3 | 0.358 | 0.305 |
| сильная (`aug_strong`): ±15°, 15 %, 50 %, яркость 0.6, стирание 0.3 | 0.338 | 0.299 |

**Вывод обратный ожидаемому:** обе метрики падают с ростом силы аугментации. Классы
различаются тем, куда повёрнута голова, а сильная аугментация калечит именно это —
голова уезжает за край или закрашивается, а метка остаётся. У `aug_strong` 63 из 86
кадров пустой кормушки отнесены к `feeding`.

## Эксперимент 3 — заморозка backbone

| запуск | accuracy | macro-F1 |
|---|---|---|
| полное дообучение (`small_100`) | 0.358 | 0.305 |
| заморожены первые 10 модулей (`frozen`) | 0.387 | 0.340 |
| заморозка + без аугментации (`frozen_augoff`) | **0.402** | **0.356** |

Заморозка помогает, оба средства против переобучения складываются. `frozen_augoff` —
лучший результат **только на своей съёмке** и опорная точка всех дополнительных
сравнений. Слабое место — `empty`: полнота 0.093.

## Дополнительные запуски

| запуск | что меняется относительно `frozen_augoff` | accuracy | macro-F1 | вывод |
|---|---|---|---|---|
| `small_100_random` | деление **по кадрам** | 0.833 | 0.827 | цена нечестного деления — 0.43 |
| `frozen_ep10` | деление по эпизодам 10 с, полоса 2 с | 0.844 | 0.829 | утечка через **сцену**, а не соседние кадры; `empty` полнота 1.000 |
| `frozen_fixval` | в проверке снегирь + дрозд + кормушка | 0.564 | 0.488 | переносится тип сцены, а не поза: `feeding` F1 0.115 |
| `frozen_drop` | дрозд убран из обучения | 0.353 | 0.300 | стало **хуже**: трудные кадры несли больше сигнала, чем шума |
| `base` | шесть мелких классов | 0.255 | 0.103 | мелкая разметка на такой выборке обходится дороже, чем даёт |
| `pretrain_stage1` | 13 видов WetlandBirds, 10 эпох | 0.858 | 0.659 | другая задача; своя константа 0.105 |
| **`pretrain_stage2`** | веса этапа 1 + дообучение на своих 3 классах | **0.510** | **0.402** | **итоговая модель** |

**Итоговая модель — `pretrain_stage2`.** Единственный из 13 запусков, обошедший
константу **и** по accuracy (+0.088), **и** по macro-F1 (+0.204). Весь прирост — в
`empty` (полнота 0.093 → 0.605). `feeding` при этом не предсказывается вовсе
(0.368 → 0.000). Прирост метрики здесь **не** означает прироста по задаче: модель
выиграла на классе, который поведением не является. Видно это только из матрицы ошибок.

macro-F1 этапа 1 (0.659) занижен механически: три вида без проверочных вырезок дают
F1 = 0, и `0.857 × 10/13 = 0.659`.

Не сделано: запуск на `birds_v1_episode_noryab` (датасет собран) и шестиклассовый
запуск в настройках `frozen --aug off`. Второй закрыл бы оговорку, что сравнение `base`
не полностью изолировано.

## Файлы

| файл | что делает |
|---|---|
| `vsyo.ps1` | очередь: сборка датасетов → `frozen_drop` → `frozen_fixval` → `base` → разбор по клипам → сводка; на время работы запрещает сон компьютера; журнал в `log_vsyo.txt` |
| `всё.bat` | двойной щелчок: запускает `vsyo.ps1` |
| `остальные_запуски.bat` | `aug_strong`, `frozen`, сборка и обучение на делении по кадрам; журнал в `log_obuchenie.txt` |

Файлы запускаются из этой папки и обращаются к скриптам соседних шагов
(`..\step4_baseline_model\train.py` и так далее).

## Как воспроизвести всё

Из `C:\Users\kkhod\claude\AIS`, пути от `AIS\data\`:

```powershell
python project1\step2_dataset\prepare_data.py --seed 5
python project1\step4_baseline_model\train.py --exp small --frac 0.33               # эксперимент 1
python project1\step4_baseline_model\train.py --exp small --frac 1.0
python project1\step4_baseline_model\train.py --exp aug --aug off                   # эксперимент 2
python project1\step4_baseline_model\train.py --exp aug --aug strong
python project1\step4_baseline_model\train.py --exp frozen                          # эксперимент 3
python project1\step4_baseline_model\train.py --exp frozen --aug off --tag augoff

python project1\step2_dataset\prepare_data.py --seed 5 --random-split
python project1\step4_baseline_model\train.py --exp small --frac 1.0 --data datasets\birds_v1_random --tag random
python project1\step2_dataset\prepare_data.py --seed 5 --episodes 10 --guard 2
python project1\step4_baseline_model\train.py --exp frozen --aug off --data datasets\birds_v1_episode --tag ep10
python project1\step2_dataset\prepare_data.py --seed 5 --drop-clips ryabinnik2686 --val-clips snegir2692,ryabinnik2686,kormushka2729
python project1\step4_baseline_model\train.py --exp frozen --aug off --data datasets\birds_v1_course3_drop --tag drop
python project1\step4_baseline_model\train.py --exp frozen --aug off --data datasets\birds_v1_fixval --tag fixval
python project1\step4_baseline_model\train.py --exp base --data datasets\birds_v1_fine

python project1\step4_baseline_model\train.py --exp pretrain --stage 1 --pretrain-data datasets\pretrain_split
python project1\step4_baseline_model\train.py --exp pretrain --stage 2              # итоговая модель

python project1\step5_metrics\svodka.py
```

Все запуски детерминированы: деление задаётся зерном, пересечение клипов проверяется при
каждой сборке.

**Отчёт:** разделы 5–8, 12.
