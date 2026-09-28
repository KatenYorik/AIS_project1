# Проект 1 — классификатор поведения птицы

Дообучение Ultralytics YOLO на собственной съёмке с методически правильным циклом:
данные → разметка → версии → эксперименты в ClearML → улучшение → развёртывание.
Задание — `AIS\notes\projects\pr01-yolo-finetuning.md`, 15 % оценки.

**Отчёт:** [`ОТЧЁТ_ПРОЕКТ1.ru.md`](ОТЧЁТ_ПРОЕКТ1.ru.md), 12 разделов.
Не заполнены группа, ссылка на ClearML и ссылка на git.

## Шаги

Папки названы по разделам задания.

| шаг | папка | что сделано | статус |
|---|---|---|---|
| 1 | [`step1_task`](step1_task/README.md) | классификация кадра: кормление / осмотр / птицы нет | готово |
| 2 | [`step2_dataset`](step2_dataset/README.md) | своя съёмка 946 кадров + открытый Visual WetlandBirds 1947 вырезок, деление по клипам | готово |
| 3 | [`step3_annotation_versioning`](step3_annotation_versioning/README.md) | разметка в своём инструменте в три прохода; экспорт для CVAT; версии v1/v2 в ClearML | разметка готова; **в CVAT не загружено** |
| 4 | [`step4_baseline_model`](step4_baseline_model/README.md) | `yolo11n-cls`, 30 эпох на CPU, журнал в ClearML | готово |
| 5 | [`step5_metrics`](step5_metrics/README.md) | accuracy + macro-F1 против константы, матрица ошибок, разбор по клипам | готово |
| 6 | [`step6_experiments`](step6_experiments/README.md) | 3 обязательных эксперимента + 7 дополнительных запусков, итоговая модель | готово |
| 7 | [`step7_training_resources`](step7_training_resources/README.md) | всё на процессоре AMD Ryzen 5 5500U | готово |
| 8 | [`step8_deployment_demo`](step8_deployment_demo/README.md) | экспорт в ONNX; живая демонстрация с камеры | экспорт готов; **демонстрация не записана** |

## Главное в числах

Проверка — 4 клипа, 204 кадра. Сильнейшая константа («всегда `empty`»):
accuracy 0.422, macro-F1 0.198.

| | accuracy | macro-F1 |
|---|---|---|
| итоговая модель `pretrain_stage2` | **0.510** | **0.402** |
| лучшая только на своей съёмке `frozen_augoff` | 0.402 | 0.356 |
| та же модель, деление **по кадрам** (нечестно) | 0.833 | 0.827 |
| деление по эпизодам 10 с | 0.844 | 0.829 |

**Главный результат** — измеренная цена неправильного деления: от 0.83 до 0.40 на тех
же кадрах. Утечка идёт через узнавание сцены, а не через соседние кадры.

**Главный изъян итоговой модели:** она не предсказывает `feeding` ни разу (F1 = 0).
Предобучение на чужих птицах дало признак «птица есть / птицы нет», а не позу.

## Как запускать

Из `C:\Users\kkhod\claude\AIS`. Пути в аргументах считаются от `AIS\data\`
(см. `common\README.md`):

```powershell
python project1\step5_metrics\svodka.py                 # таблица по всем 13 запускам
python project1\step2_dataset\split_help.py --check     # 10 тестов деления по клипам
python project1\step4_baseline_model\train.py --exp pretrain --stage 2   # итоговая модель
```

Данные и результаты — `AIS\data\`. Научный анализ той же разметки —
`AIS\scientific_question\`.
