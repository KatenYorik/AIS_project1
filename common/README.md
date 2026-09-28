# common — общее для всех шагов

| файл | что делает |
|---|---|
| `aispaths.py` | **единственное место, где записано, где лежат данные.** Им пользуются все скрипты шагов |
| `check_env.py` | проверка окружения: какие пакеты стоят, есть ли ffmpeg, ROS 2, видеокарта |
| `setup_windows.ps1`, `setup_windows.bat` | установка пакетов для Проекта 1 и панели Проекта 2 на Windows (ultralytics, onnx, onnxruntime, clearml, gradio, opencv) |
| `УСТАНОВКА.ru.md` | что и куда ставить: Windows для обучения, WSL для ROS 2 |

```powershell
cd C:\Users\kkhod\claude\AIS
python common\check_env.py
powershell -ExecutionPolicy Bypass -File common\setup_windows.ps1
```

---

## `aispaths.py`: как скрипты находят данные

После раскладки по шагам скрипты лежат в разных папках, а данные — в одной
`AIS\data\`. Чтобы старые команды работали с прежними аргументами, скрипт в начале
переходит в `AIS\data\`:

```python
import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
```

Этот блок стоит в начале каждого скрипта, работающего с данными. Строка с `next(...)`
ищет папку `common` вверх по дереву, поэтому скрипт можно переносить на любую глубину.

| что | значение |
|---|---|
| `ROOT` | `AIS\` |
| `DATA`, `DATASETS`, `RUNS`, `RESULTS`, `LABELS` | `data\`, `data\datasets\`, `data\runs\`, `data\results\`, `data\labels_all.csv` |
| `FINAL_PT`, `FINAL_ONNX` | веса итоговой модели `pretrain_stage2` |
| `ROS_PKG` | `project2\ros2_ws\src\birdcls\birdcls\` — там `efe.py` |
| `WETLANDBIRDS`, `VIDEOS` | `AIS\wetlandbirds\`, `AIS\птицы\` |
| `to_data()` | перейти в `AIS\data\` |
| `resolve_data(p)` | путь как есть, если существует; иначе — от `AIS\data\` |
| `add_script_dir(__file__)` | сделать соседние скрипты импортируемыми |
| `add_ros_pkg()` | сделать `efe.py` импортируемым вне ROS |

**Следствие, которое надо помнить.** Относительный путь в аргументе считается от
`AIS\data\`, а не от текущей папки. Для кадров, разметки, весов и датасетов это и
нужно. Путь к чему-то **вне** `data\` давать абсолютным или от `data\`
(`..\wetlandbirds\bounding_boxes.csv` = `AIS\wetlandbirds\bounding_boxes.csv`).

**Исключение — панель Gradio.** Ей нельзя переходить в `data\` целиком: у неё
`--source` может быть путём к видео относительно текущей папки. Поэтому панель
пропускает через `resolve_data` только `--model` и `--confusion`.

**Проверено 14.09.2026.** После переноса новые скрипты, запущенные из
`C:\Users\kkhod`, дают вывод, совпадающий строка в строку со старыми из резервной
копии: `svodka`, `split_help --check`, `dataset --check`, `decision_rate`,
`po_klipam` на итоговой модели, `analyse_new`, `gaze`, `dwell`, `group_own`,
`lateral_summary`, `group_summary`, `wetlandbirds`, `estimate_B`. Скрипты,
которые пишут данные, проверены только через `--help`.

**Новый скрипт, работающий с данными**, подключает этот блок. Данные в папки шагов
не кладутся.
