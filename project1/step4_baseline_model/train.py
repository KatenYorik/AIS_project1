# -*- coding: utf-8 -*-
"""Шаг 6: обучение классификатора + три эксперимента курса. ClearML + YOLO-cls.

Готово к запуску, как только соберётся datasets/birds_v1_course3. Ничего в нём не надо
дописывать — в отличие от split_by_clip в dataset.py, который пишешь ты.

    pip install ultralytics clearml
    clearml-init                       # один раз, ключи с app.clear.ml

    python train.py --exp small --frac 0.33         # эксперимент 1 курса: часть данных
    python train.py --exp aug --aug strong          # эксперимент 2 курса: аугментация
    python train.py --exp frozen                    # эксперимент 3 курса: замороженный backbone

    python train.py --exp base                      # эксперимент 0: своя съёмка
    python train.py --exp flip                      # эксперимент 3: fliplr=0.5
    python train.py --exp coarse                    # эксперимент 2: грубые классы
    python train.py --exp pretrain --stage 1        # эксперимент 1, этап 1
    python train.py --exp pretrain --stage 2        # эксперимент 1, этап 2

Ожидаемая структура (её делает prepare_data.py):

    datasets/birds_v1_course3/train/<класс>/*.jpg      три зачётных класса
    datasets/birds_v1_fine/train/<класс>/*.jpg         шесть мелких
    datasets/pretrain/<грубый класс>/*.jpg     # только для --exp pretrain
"""
from __future__ import annotations
import sys as _sys, pathlib as _pl  # общие пути AIS, см. common/aispaths.py
_sys.path.insert(0, str(next(_p / "common" for _p in _pl.Path(__file__).resolve().parents
                            if (_p / "common" / "aispaths.py").is_file())))
import aispaths
aispaths.to_data()  # данные, runs, results и пути в аргументах — от AIS/data
import sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

import argparse, collections, json, os, shutil, sys

# мелкий класс → грубый. Нужно для эксперимента 2: чтобы сравнить модели с разным
# числом классов, предсказания мелкой модели схлопываются в грубые.
# Три класса зачётной версии (COURSEWORK_PLAN.ru.md): feeding / alert / empty.
# Мелкая разметка сворачивается в них без потерь — ради этого она и делалась мелкой.
COURSE3 = {
    "head_down":     "feeding",
    "handling":      "feeding",
    "head_up_ahead": "alert",
    "head_up_turnL": "alert",
    "head_up_turnR": "alert",
    "no_bird":       "empty",
    # transit и ambiguous в зачётные три класса не входят и отбрасываются
}

COARSE = {
    "head_down":     "feeding",
    "handling":      "feeding",
    "head_up_ahead": "alert",
    "head_up_turnL": "alert",
    "head_up_turnR": "alert",
    "transit":       "transit",
    "no_bird":       "no_bird",
    "ambiguous":     "ambiguous",
}

EXPS = {
    # имя      fliplr  классы   комментарий для отчёта
    # --- три эксперимента зачётного чек-листа
    "small":    (0.0, "course3", "часть обучающей выборки против всей: размер против точности"),
    "aug":      (0.0, "course3", "аугментация выкл / обычная / сильная на почти-дубликатах"),
    "frozen":   (0.0, "course3", "замороженный backbone против полного дообучения"),
    # --- дополнительные, по научной части
    "base":     (0.0, "fine",   "своя съёмка, 8 мелких классов"),
    "flip":     (0.5, "fine",   "то же + зеркальная аугментация (должна испортить turnL/turnR)"),
    "coarse":   (0.0, "coarse", "те же кадры, свёрнутые в грубые классы"),
    "pretrain": (0.0, "fine",   "предобучение на WetlandBirds + дообучение на своей съёмке"),
}


def build_coarse_copy(src, dst, mapping=None, drop=True):
    """Копия датасета со свёрнутыми классами. mapping=None → грубые 5, иначе свои."""
    M = mapping if mapping is not None else COARSE
    if os.path.exists(dst): shutil.rmtree(dst)
    n = 0
    for split in ("train", "val"):
        for cls in sorted(os.listdir(os.path.join(src, split))):
            tgt = M.get(cls)
            if tgt is None:
                if drop and mapping is not None: continue
                tgt = cls
            out = os.path.join(dst, split, tgt)
            os.makedirs(out, exist_ok=True)
            for f in os.listdir(os.path.join(src, split, cls)):
                # имя клипа в начале файла сохраняется — разделение по клипам не ломается
                shutil.copy2(os.path.join(src, split, cls, f), os.path.join(out, f))
                n += 1
    print(f"грубая копия: {n} кадров → {dst}")
    return dst


def baseline(root):
    """Базовое решение: всегда самый частый класс обучающей выборки."""
    tr = collections.Counter()
    for cls in os.listdir(os.path.join(root, "train")):
        tr[cls] = len(os.listdir(os.path.join(root, "train", cls)))
    top = tr.most_common(1)[0][0]
    va = collections.Counter()
    for cls in os.listdir(os.path.join(root, "val")):
        va[cls] = len(os.listdir(os.path.join(root, "val", cls)))
    n = max(sum(va.values()), 1)
    acc = va[top] / n
    print(f"базовое решение: всегда «{top}» (самый частый в обучении) → "
          f"accuracy {acc:.3f} ({va[top]} из {n})")

    # При делении по клипам самый частый класс в обучении и в проверке могут не
    # совпадать: клип целиком уносит свои кадры. Тогда честная планка выше —
    # это лучшая из констант НА ПРОВЕРКЕ. Её и надо перебивать в отчёте.
    btop, bn = va.most_common(1)[0]
    if btop != top:
        print(f"сильнейшая константа на проверке: всегда «{btop}» → "
              f"accuracy {bn / n:.3f} ({bn} из {n})  <- вот эту планку и бить")
    return top, acc, btop, bn / n


def metrics(model, root, split="val", coarse=False):
    """accuracy / precision / recall / F1 по классам + матрица ошибок.

    Считается вручную, а не через model.val(), потому что для эксперимента 2 нужно
    схлопывать предсказания в грубые классы — этого val() не умеет.
    """
    names = sorted(os.listdir(os.path.join(root, split)))
    y_true, y_pred = [], []
    for cls in names:
        d = os.path.join(root, split, cls)
        files = [os.path.join(d, f) for f in sorted(os.listdir(d))]
        for i in range(0, len(files), 64):
            for r in model.predict(files[i:i+64], verbose=False):
                p = r.names[int(r.probs.top1)]
                m = COURSE3 if coarse == "course3" else COARSE
                y_true.append(m.get(cls, cls) if coarse else cls)
                y_pred.append(m.get(p, p) if coarse else p)

    labels = sorted(set(y_true) | set(y_pred))
    idx = {c: i for i, c in enumerate(labels)}
    cm = [[0]*len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred): cm[idx[t]][idx[p]] += 1

    acc = sum(cm[i][i] for i in range(len(labels))) / max(len(y_true), 1)
    print(f"\naccuracy: {acc:.3f}  ({len(y_true)} кадров)")
    print(f"\n{'класс':16s} {'точность':>9s} {'полнота':>9s} {'F1':>7s} {'кадров':>7s}")
    f1s, sup = [], []
    for c in labels:
        i = idx[c]
        tp = cm[i][i]
        fp = sum(cm[j][i] for j in range(len(labels))) - tp
        fn = sum(cm[i]) - tp
        pr = tp/(tp+fp) if tp+fp else 0.0
        rc = tp/(tp+fn) if tp+fn else 0.0
        f1 = 2*pr*rc/(pr+rc) if pr+rc else 0.0
        f1s.append(f1); sup.append(sum(cm[i]))
        print(f"{c:16s} {pr:9.3f} {rc:9.3f} {f1:7.3f} {sum(cm[i]):7d}")
    macro = sum(f1s)/len(f1s)
    weigh = sum(f*s for f, s in zip(f1s, sup))/max(sum(sup), 1)
    print(f"\nmacro-F1 {macro:.3f}   взвешенный F1 {weigh:.3f}")

    print("\nматрица ошибок (строка — истина, столбец — предсказание)")
    w = max(len(c) for c in labels)
    print(" "*(w+1) + " ".join(f"{c[:6]:>6s}" for c in labels))
    for c in labels:
        print(f"{c:{w}s} " + " ".join(f"{v:6d}" for v in cm[idx[c]]))

    # для отчёта важнее всего эта пара — на ней видно вред fliplr
    if "head_up_turnL" in idx and "head_up_turnR" in idx:
        L, R = idx["head_up_turnL"], idx["head_up_turnR"]
        sw = cm[L][R] + cm[R][L]
        tot = sum(cm[L]) + sum(cm[R])
        print(f"\nпутаница turnL ↔ turnR: {sw} из {tot} ({sw/max(tot,1):.3f}) "
              f"← ключевое число эксперимента 3")
    return {"accuracy": acc, "macro_f1": macro, "weighted_f1": weigh,
            "labels": labels, "confusion": cm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", choices=list(EXPS), default="base")
    ap.add_argument("--stage", type=int, default=0, help="для pretrain: 1 или 2")
    ap.add_argument("--data", default="datasets/birds_v1_course3")
    ap.add_argument("--pretrain-data", default="datasets/pretrain")
    ap.add_argument("--model", default="yolo11n-cls.pt")
    ap.add_argument("--epochs", type=int, default=0, help="0 = по умолчанию для этапа")
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--frac", type=float, default=1.0,
                    help="доля обучающей выборки (эксперимент 1 курса)")
    ap.add_argument("--aug", choices=["off", "normal", "strong"], default="normal",
                    help="сила аугментации (эксперимент 2 курса)")
    ap.add_argument("--freeze", type=int, default=None,
                    help="сколько слоёв заморозить (эксперимент 3 курса)")
    ap.add_argument("--tag", default="", help="приписка к имени запуска, чтобы не затирать прошлый")
    ap.add_argument("--no-clearml", action="store_true")
    a = ap.parse_args()

    fliplr, level, note = EXPS[a.exp]
    root = a.data
    if level == "coarse":
        root = build_coarse_copy(a.data, a.data + "_coarse")
    elif level == "course3":
        # Данные могут прийти уже свёрнутыми (datasets/birds_v1_course3) или мелкими
        # (datasets/birds_v1_fine). В первом случае свёртка не нужна: COURSE3 не знает
        # ключей feeding/alert/empty и выбросил бы все кадры до единого.
        if not os.path.isdir(os.path.join(a.data, "train")):
            sys.exit(f"нет папки {a.data}/train — сначала  python prepare_data.py")
        have = set(os.listdir(os.path.join(a.data, "train")))
        if have <= {"feeding", "alert", "empty"}:
            root = a.data
            print(f"данные уже в зачётных классах: {sorted(have)}")
        else:
            root = build_coarse_copy(a.data, a.data + "_course3", COURSE3)
        if a.exp == "frozen" and a.freeze is None: a.freeze = 10

    if a.exp == "pretrain" and a.stage == 1:
        root = a.pretrain_data
        if not os.path.isdir(os.path.join(root, "train")):
            sys.exit(f"{root} без train/val — сначала build_pretrain_set.py, "
                     f"потом dataset.py --sorted {root} --out {root}_split")

    if not os.path.isdir(root): sys.exit(f"нет папки {root}")

    name = a.exp if a.stage == 0 else f"{a.exp}_stage{a.stage}"
    if a.exp == "small": name += f"_{int(a.frac*100)}"
    if a.exp == "aug": name += f"_{a.aug}"
    if a.tag: name += f"_{a.tag}"

    task = None
    if not a.no_clearml:
        try:
            from clearml import Task
            task = Task.init(project_name="AIS-birds", task_name=name,
                             output_uri=False)
            task.connect({"эксперимент": a.exp, "смысл": note, "fliplr": fliplr,
                          "уровень классов": level, "данные": root})
            # две версии датасета — требование курса
            try:
                from clearml import Dataset
                ds = Dataset.create(dataset_project="AIS-birds",
                                    dataset_name=os.path.basename(root))
                ds.add_files(root); ds.upload(); ds.finalize()
                print("датасет зарегистрирован в ClearML:", ds.id)
            except Exception as e:
                print("датасет в ClearML не зарегистрирован:", e)
        except ImportError:
            print("clearml не установлен — обучение пойдёт без него")

    print(f"\n=== {name}: {note}")
    print(f"данные: {root}   fliplr={fliplr}")
    base_cls, base_acc, hard_cls, hard_acc = baseline(root)

    from ultralytics import YOLO
    weights = a.model
    if a.exp == "pretrain" and a.stage == 2:
        w = "runs/classify/pretrain_stage1/weights/best.pt"
        if not os.path.exists(w):
            sys.exit("сначала --exp pretrain --stage 1")
        weights = w
        print("веса взяты с этапа 1")

    epochs = a.epochs or (10 if (a.exp == "pretrain" and a.stage == 1) else 30)
    model = YOLO(weights)
    # аугментация тремя ступенями — это и есть эксперимент 2 чек-листа
    AUG = {"off":    dict(degrees=0.0, translate=0.0, scale=0.0, hsv_v=0.0, erasing=0.0),
           "normal": dict(degrees=5.0, translate=0.05, scale=0.2, hsv_v=0.3, erasing=0.0),
           "strong": dict(degrees=15.0, translate=0.15, scale=0.5, hsv_v=0.6, erasing=0.3)}
    extra = dict(AUG[a.aug])
    if a.frac < 1.0: extra["fraction"] = a.frac
    if a.freeze is not None: extra["freeze"] = a.freeze
    print("параметры запуска:", {"aug": a.aug, "frac": a.frac, "freeze": a.freeze})
    model.train(data=os.path.abspath(root), epochs=epochs, imgsz=a.imgsz,
                batch=a.batch, device=a.device, name=name, exist_ok=True,
                fliplr=fliplr, flipud=0.0, auto_augment=None, **extra)

    best = YOLO(f"runs/classify/{name}/weights/best.pt")
    res = metrics(best, root, "val", coarse=False)
    res.update(experiment=a.exp, note=note, fliplr=fliplr,
               baseline_class=base_cls, baseline_accuracy=base_acc,
               strongest_constant_class=hard_cls, strongest_constant_accuracy=hard_acc)

    # эксперимент 2: мелкую модель мерим ещё и на грубом уровне — общий знаменатель
    if level == "fine" and a.exp != "pretrain":
        print("\n--- те же предсказания, свёрнутые в ТРИ зачётных класса")
        print("    это число сравнивается напрямую с --exp small/aug/frozen:")
        print("    видно, сколько стоит мелкая разметка на том же материале")
        res["course3_view"] = metrics(best, root, "val", coarse="course3")

    os.makedirs("results", exist_ok=True)
    with open(f"results/{name}.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"\nсохранено results/{name}.json")
    print(f"выигрыш над базовым решением «всегда {base_cls}»: "
          f"{res['accuracy'] - base_acc:+.3f} accuracy")
    if hard_cls != base_cls:
        print(f"выигрыш над сильнейшей константой «всегда {hard_cls}» ({hard_acc:.3f}): "
              f"{res['accuracy'] - hard_acc:+.3f}  <- это число для отчёта")
    if res["macro_f1"] < 0.45:
        print("\nmacro-F1 низкий: модель почти наверняка свалилась в один класс.\n"
              "Смотри матрицу ошибок — если целый столбец пуст, этот класс не\n"
              "предсказывается никогда. Для эксперимента «часть данных» это\n"
              "нормальный и ожидаемый результат, а не поломка.")
    if task: task.close()


if __name__ == "__main__":
    main()
