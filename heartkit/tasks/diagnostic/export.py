import logging
import os
import shutil

import keras
import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score

import keras_edge as kedge
from ...defines import HKExportParams
from ...utils import setup_logger
from ..utils import load_datasets
from .datasets import load_test_dataset

logger = setup_logger(__name__)


def export(params: HKExportParams):
    """Export model

    Args:
        params (HKExportParams): Deployment parameters
    """
    params.threshold = params.threshold or 0.5

    os.makedirs(params.job_dir, exist_ok=True)
    logger.info(f"Creating working directory in {params.job_dir}")

    handler = logging.FileHandler(params.job_dir / "export.log", mode="w")
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    tfl_model_path = params.job_dir / "model.tflite"
    tflm_model_path = params.job_dir / "model_buffer.h"

    # classes = sorted(list(set(params.class_map.values())))
    # class_names = params.class_names or [f"Class {i}" for i in range(params.num_classes)]

    feat_shape = (params.frame_size, 1)
    class_shape = (params.num_classes,)

    ds_spec = (
        tf.TensorSpec(shape=feat_shape, dtype="float32"),
        tf.TensorSpec(shape=class_shape, dtype="int32"),
    )

    datasets = load_datasets(datasets=params.datasets)

    test_ds = load_test_dataset(datasets=datasets, params=params, ds_spec=ds_spec)
    test_x, test_y = next(test_ds.batch(params.test_size).as_numpy_iterator())

    # Load model and set fixed batch size of 1
    model = kedge.models.load_model(params.model_file)

    inputs = keras.Input(shape=ds_spec[0].shape, batch_size=1, name="input", dtype=ds_spec[0].dtype)
    model(inputs)

    flops = kedge.metrics.flops.get_flops(model, batch_size=1, fpath=params.job_dir / "model_flops.log")
    model.summary(print_fn=logger.info)
    logger.info(f"Model requires {flops/1e6:0.2f} MFLOPS")

    logger.info(f"Converting model to TFLite (quantization={params.quantization.mode})")
    tflite = kedge.converters.tflite.TfLiteKerasConverter(model=model)
    tflite.convert(
        test_x=test_x,
        quantization=params.quantization.mode,
        io_type=params.quantization.io_type,
        use_concrete=params.quantization.concrete,
        strict=not params.quantization.fallback,
    )

    if params.quantization.debug:
        quant_df = tflite.debug_quantization()
        quant_df.to_csv(params.job_dir / "quant.csv")

    # Save TFLite model
    logger.info(f"Saving TFLite model to {tfl_model_path}")
    tflite.export(tfl_model_path)

    # Save TFLM model
    logger.info(f"Saving TFL micro model to {tflm_model_path}")
    tflite.export_header(tflm_model_path, name=params.tflm_var_name)

    # Verify TFLite results match TF results
    logger.info("Validating model results")
    y_true = test_y
    y_pred_tf = model.predict(test_x) >= params.threshold
    y_pred_tfl = tflite.predict(x=test_x) >= params.threshold

    tf_acc = np.sum(y_true == y_pred_tf) / y_true.size
    tf_f1 = f1_score(y_true, y_pred_tf, average="weighted")
    logger.info(f"[TF SET] ACC={tf_acc:.2%}, F1={tf_f1:.2%}")

    tfl_acc = np.sum(y_true == y_pred_tfl) / y_true.size
    tfl_f1 = f1_score(y_true, y_pred_tfl, average="weighted")
    logger.info(f"[TFL SET] ACC={tfl_acc:.2%}, F1={tfl_f1:.2%}")

    # Check accuracy hit
    tfl_acc_drop = max(0, tf_acc - tfl_acc)
    if params.val_acc_threshold is not None and (1 - tfl_acc_drop) < params.val_acc_threshold:
        logger.warning(f"TFLite accuracy dropped by {tfl_acc_drop:0.2%}")
    elif params.val_acc_threshold:
        logger.info(f"Validation passed ({tfl_acc_drop:0.2%})")

    if params.tflm_file and tflm_model_path != params.tflm_file:
        logger.info(f"Copying TFLM header to {params.tflm_file}")
        shutil.copyfile(tflm_model_path, params.tflm_file)

    tflite.cleanup()
