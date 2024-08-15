import os

import keras
import numpy as np
import sklearn.utils
import wandb
from wandb.keras import WandbMetricsLogger, WandbModelCheckpoint
import neuralspot_edge as nse

from ...defines import HKTaskParams
from ...datasets import DatasetFactory
from .datasets import load_train_datasets
from ...models import ModelFactory
from ...utils import dark_theme, setup_plotting


class TermineTrainingError(Exception):
    pass


class TerminateTrainingCallback(keras.callbacks.Callback):
    def on_train_end(self, epoch, logs=None):
        raise TermineTrainingError("Training stopped by KillerCallBack")


def train(params: HKTaskParams):
    """Train  model

    Args:
        params (HKTaskParams): Training parameters
    """
    os.makedirs(params.job_dir, exist_ok=True)

    logger = nse.utils.setup_logger(__name__, level=params.verbose, file_path=params.job_dir / "train.log")
    logger.debug(f"Creating working directory in {params.job_dir}")

    params.seed = nse.utils.set_random_seed(params.seed)
    logger.debug(f"Random seed {params.seed}")

    with open(params.job_dir / "train_config.json", "w", encoding="utf-8") as fp:
        fp.write(params.model_dump_json(indent=2))

    if nse.utils.env_flag("WANDB"):
        wandb.init(
            project=params.project,
            entity="ambiq",
            dir=params.job_dir,
        )
        wandb.config.update(params.model_dump())
    # END IF

    classes = sorted(set(params.class_map.values()))
    class_names = params.class_names or [f"Class {i}" for i in range(params.num_classes)]

    feat_shape = (params.frame_size, 1)

    datasets = [DatasetFactory.get(ds.name)(**ds.params) for ds in params.datasets]

    train_ds, val_ds = load_train_datasets(datasets=datasets, params=params)

    y_true = np.concatenate([y for _, y in val_ds.as_numpy_iterator()])
    y_true = np.argmax(y_true, axis=-1).flatten()

    class_weights = 0.25
    if params.class_weights == "balanced":
        class_weights = sklearn.utils.compute_class_weight("balanced", classes=np.array(classes), y=y_true)
        class_weights = (class_weights + class_weights.mean()) / 2  # Smooth out
        class_weights = class_weights.tolist()
    # END IF
    logger.debug(f"Class weights: {class_weights}")

    inputs = keras.Input(shape=feat_shape, name="input", dtype="float32")

    # Load existing model
    if params.resume and params.model_file:
        logger.debug(f"Loading model from file {params.model_file}")
        model = nse.models.load_model(params.model_file)
        params.model_file = None
    else:
        logger.debug("Creating model from scratch")
        if params.architecture is None:
            raise ValueError("Model architecture must be specified")
        model = ModelFactory.get(params.architecture.name)(
            x=inputs,
            params=params.architecture.params,
            num_classes=params.num_classes,
        )
    # END IF

    flops = nse.metrics.flops.get_flops(model, batch_size=1, fpath=params.job_dir / "model_flops.log")

    t_mul = 1
    first_steps = (params.steps_per_epoch * params.epochs) / (np.power(params.lr_cycles, t_mul) - t_mul + 1)
    scheduler = keras.optimizers.schedules.CosineDecayRestarts(
        initial_learning_rate=params.lr_rate,
        first_decay_steps=np.ceil(first_steps),
        t_mul=t_mul,
        m_mul=0.5,
    )

    optimizer = keras.optimizers.Adam(scheduler)
    loss = keras.losses.CategoricalFocalCrossentropy(from_logits=True, alpha=class_weights)

    metrics = [
        keras.metrics.CategoricalAccuracy(name="acc"),
        keras.metrics.F1Score(name="f1", average="weighted"),
    ]

    if params.resume and params.weights_file and params.weights_file.exists():
        logger.debug(f"Hydrating model weights from file {params.weights_file}")
        model.load_weights(params.weights_file)

    if params.model_file is None:
        params.model_file = params.job_dir / "model.keras"

    model.compile(optimizer=optimizer, loss=loss, metrics=metrics)
    model.summary(print_fn=logger.debug)
    logger.debug(f"Model requires {flops/1e6:0.2f} MFLOPS")

    ModelCheckpoint = keras.callbacks.ModelCheckpoint
    if nse.utils.env_flag("WANDB"):
        ModelCheckpoint = WandbModelCheckpoint
    model_callbacks = [
        keras.callbacks.EarlyStopping(
            monitor=f"val_{params.val_metric}",
            patience=max(int(0.25 * params.epochs), 1),
            mode="max" if params.val_metric == "f1" else "auto",
            restore_best_weights=True,
            verbose=min(params.verbose - 1, 1),
        ),
        ModelCheckpoint(
            filepath=str(params.model_file),
            monitor=f"val_{params.val_metric}",
            save_best_only=True,
            mode="max" if params.val_metric == "f1" else "auto",
            verbose=min(params.verbose - 1, 1),
        ),
        keras.callbacks.CSVLogger(params.job_dir / "history.csv"),
    ]
    if nse.utils.env_flag("TENSORBOARD"):
        model_callbacks.append(
            keras.callbacks.TensorBoard(
                log_dir=params.job_dir,
                write_steps_per_second=True,
            )
        )
    if nse.utils.env_flag("WANDB"):
        model_callbacks.append(WandbMetricsLogger())

    # NOTE: A bug w/ Keras/TF causes model.fit to hang on last epoch.
    # This workaround terminates training on KeyboardInterrupt or last epoch.
    # model_callbacks.append(TerminateTrainingCallback())

    try:
        history = model.fit(
            train_ds,
            steps_per_epoch=params.steps_per_epoch,
            verbose=params.verbose,
            epochs=params.epochs,
            validation_data=val_ds,
            callbacks=model_callbacks,
        )

    except (KeyboardInterrupt, TermineTrainingError):
        logger.warning("Stopping training due to interrupt")

    logger.debug(f"Model saved to {params.model_file}")

    setup_plotting(dark_theme)
    if history:
        nse.plotting.plot_history_metrics(
            history.history,
            metrics=["loss", "acc"],
            save_path=params.job_dir / "history.png",
            stack=True,
            figsize=(9, 5),
        )

    # Get full validation results
    logger.debug("Performing full validation")
    y_pred = np.argmax(model.predict(val_ds), axis=-1)

    cm_path = params.job_dir / "confusion_matrix.png"
    nse.plotting.confusion_matrix_plot(y_true, y_pred, labels=class_names, save_path=cm_path, normalize="true")
    if nse.utils.env_flag("WANDB"):
        conf_mat = wandb.plot.confusion_matrix(preds=y_pred, y_true=y_true, class_names=class_names)
        wandb.log({"conf_mat": conf_mat})
    # END IF

    # Summarize results
    rst = model.evaluate(val_ds, return_dict=True)
    logger.info("[VAL SET] " + ", ".join(f"{k.upper()}={v:.2%}" for k, v in rst.items()))

    # os.abort()
    # END TRY
