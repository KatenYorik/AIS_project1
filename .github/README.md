# Поведение птицы: от разметки кадров до робота в Gazebo

Курсовые проекты курса **AIS (Artificial Intelligence Software)**, МФТИ, 2026.
Автор — Ходарева Екатерина.

Собственная архивная съёмка птиц у кормушки размечена по кадрам. На ней дообучен
классификатор YOLO (Проект 1), а в Проекте 2 он в формате ONNX управляет роботом через
ROS 2: turtlesim и TurtleBot3 в Gazebo.

## Ссылки

| что | где |
|---|---|
| Отчёт Проекта 1 | [`project1/ОТЧЁТ_ПРОЕКТ1.ru.md`](../project1/ОТЧЁТ_ПРОЕКТ1.ru.md) |
| Отчёт Проекта 2 | [`project2/ОТЧЁТ_ПРОЕКТ2.ru.md`](../project2/ОТЧЁТ_ПРОЕКТ2.ru.md) |
| ClearML, проект `AIS-birds` | `<ССЫЛКА ВПИСАТЬ>` |
| Видео: Gazebo | `<ССЫЛКА ВПИСАТЬ>` |
| Видео: turtlesim | `<ССЫЛКА ВПИСАТЬ>` |
| Итоговая модель ONNX | [`data/runs/classify/pretrain_stage2/weights/best.onnx`](../data/runs/classify/pretrain_stage2/weights/best.onnx) |

## Главное

**Проект 1.** Три класса: кормление, осмотр, птицы нет. 792 кадра, 16 клипов, деление на
обучение и проверку **по клипам**. Итоговая модель — `yolo11n-cls`, предобученная на
открытом Visual WetlandBirds и дообученная на своей съёмке: **accuracy 0.510, macro-F1
0.402** при константе 0.422 / 0.198.

Главный результат — измеренная цена неправильного деления: та же модель на тех же кадрах
даёт 0.833 при делении по кадрам и 0.402 по клипам. Утечка идёт через узнавание сцены.

**Проект 2.** Цепочка `camera_publisher → classifier_node (onnxruntime) → controller_node →
/cmd_vel`, панель Gradio. Контроллер выбирает действие — подъехать, стоять, отъехать —
минимизацией ожидаемой свободной энергии, с порогом уверенности. ONNX совпадает с PyTorch
до 2·10⁻⁶. Демонстрация — все три действия в turtlesim и в Gazebo Sim 8 с TurtleBot3.

## Устройство репозитория

Папки шагов названы по разделам заданий. В каждой — `README.md`: что требует задание,
что сделано, файлы, команды, числа.

```
project1/                  Проект 1 — классификатор
  step1_task … step8_deployment_demo
project2/                  Проект 2 — ROS 2, ONNX, Gradio, Gazebo
  ros2_ws/src/birdcls/     пакет ROS 2
  step1_task_design … step8_demo
scientific_question/       научная часть поверх той же разметки
common/aispaths.py         где лежат данные; все скрипты работают через него
data/                      разметка, метрики, журналы демо, итоговый ONNX
```

**Чего нет в репозитории** — кадров, собранных датасетов, весов `.pt` и видео. Датасеты
версионируются в ClearML (`birds` 1.0.0 и 2.0.0), видео — по ссылкам выше.

## Запуск

Python 3.11, ultralytics, onnxruntime, gradio, clearml (`common/setup_windows.ps1`).
Для Проекта 2 — WSL, Ubuntu 24.04, ROS 2 Jazzy (`common/УСТАНОВКА.ru.md`).

```powershell
python project1/step5_metrics/svodka.py                  # метрики всех 13 запусков
python project1/step2_dataset/split_help.py --check      # тесты деления по клипам
```

```bash
bash project2/step8_demo/demo_gazebo.sh                  # Gazebo + цепочка + панель
bash project2/step8_demo/demo_turtle.sh                  # то же в turtlesim
```

Пути в аргументах скриптов считаются от `data/` (см. `common/README.md`).
