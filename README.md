
<p align="center">
  <a href="https://github.com/AmbiqAI/heartkit"><img src="./docs/assets/heartkit-banner.png" alt="HeartKit"></a>
</p>

---

**Documentation**: <a href="https://ambiqai.github.io/heartkit" target="_blank">https://ambiqai.github.io/heartkit</a>

**Source Code**: <a href="https://github.com/AmbiqAI/heartkit" target="_blank">https://github.com/AmbiqAI/heartkit</a>

---

HeartKit is an AI Development Kit (ADK) that enables developers to easily train and deploy real-time __heart-monitoring__ models onto [Ambiq's family of ultra-low power SoCs](https://ambiq.com/soc/). The kit provides a variety of datasets, efficient model architectures, and heart-related tasks. In addition, HeartKit provides optimization and deployment routines to generate efficient inference models. Finally, the kit includes a number of pre-trained models and task-level demos to showcase the capabilities.

**Key Features:**

* **Real-time**: Inference is performed in real-time on battery-powered, edge devices.
* **Efficient**: Leverage Ambiq's ultra low-power SoCs for extreme energy efficiency.
* **Extensible**: Easily add new tasks, models, and datasets to the framework.
* **Open Source**: HeartKit is open source and available on GitHub.


## <span class="sk-h2-span">Requirements

* [Python ^3.11+](https://www.python.org)
* [Poetry ^1.6.1+](https://python-poetry.org/docs/#installation)

The following are also required to compile/flash the binary for the EVB demo:

* [Arm GNU Toolchain ^12.2](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
* [Segger J-Link ^7.92](https://www.segger.com/downloads/jlink/)

!!! note
    A [VSCode Dev Container](https://code.visualstudio.com/docs/devcontainers/containers) is also available and defined in [./.devcontainer](https://github.com/AmbiqAI/heartkit/tree/main/.devcontainer).

## <span class="sk-h2-span">Installation</span>

To get started, first install the local python package `heartkit` along with its dependencies via `PyPi`:

```bash
$ pip install heartkit
```

Alternatively, you can install the package from source by cloning the repository and running the following command:

```bash
git clone https://github.com/AmbiqAI/heartkit.git
cd heartkit
poetry install
```

---

## <span class="sk-h2-span">Usage</span>

__HeartKit__ can be used as either a CLI-based tool or as a Python package to perform advanced development. In both forms, HeartKit exposes a number of modes and tasks outlined below. In addition, by leveraging highly-customizable configurations, HeartKit can be used to create custom workflows for a given application with minimal coding. Refer to the [Quickstart](https://ambiqai.github.io/heartkit/quickstart/) to quickly get up and running in minutes.

---

## <span class="sk-h2-span">Tasks</span>

__HeartKit__ includes a number of built-in **tasks**. Each task provides reference routines for training, evaluating, and exporting the model. The routines can be customized by providing a configuration file or by setting the parameters directly in the code. Additional tasks can be easily added to the __HeartKit__ framework by creating a new task class and registering it to the __task factory__.

- **Denoise**: Remove noise and artifacts from signals
- **Segmentation**: Perform ECG/PPG based segmentation
- **Rhythm**: Heart rhythm detection (AFIB, AFL)
- **Beat**: Classify individual beats (NORM, PAC, PVC)
- **BYOT**: Bring-Your-Own-Task (BYOT) to create custom tasks

---

## <span class="sk-h2-span">Modes</span>

__HeartKit__ provides a number of **modes** that can be invoked for a given task. These modes can be accessed via the CLI or directly from the `task` within the Python package.

- **Download**: Download specified datasets
- **Train**: Train a model for specified task and datasets
- **Evaluate**: Evaluate a model for specified task and datasets
- **Export**: Export a trained model to TensorFlow Lite and TFLM
- **Demo**: Run task-level demo on PC or remotely on Ambiq EVB

---

## <span class="sk-h2-span">Datasets</span>

__HeartKit__ exposes several open-source datasets for training each of the HeartKit tasks via a __dataset factory__. For certain tasks, we also provide synthetic data provided by [PhysioKit](https://ambiqai.github.io/physiokit) to help improve model generalization. Each dataset has a corresponding Python class to aid in downloading and generating data for the given task. Additional datasets can be easily added to the HeartKit framework by creating a new dataset class and registering it to the dataset factory.

* **Icentia11k**: 11-lead ECG data collected from 11,000 subjects captured continously over two weeks.
* **LUDB**: 200 ten-second 12-lead ECG records w/ annotated P-wave, QRS, and T-wave boundaries.
* **QTDB**: 100+ fifteen-minute two-lead ECG recordings w/ annotated P-wave, QRS, and T-wave boundaries.
* **LSAD**: 10-second, 12-lead ECG dataset collected from 45,152 subjects w/ over 100 scp codes.
* **PTB-XL**: 10-second, 12-lead ECG dataset collected from 18,885 subjects w/ 72 different diagnostic classes.
* **Synthetic**: A synthetic dataset generator from [PhysioKit](https://ambiqai.github.io/physiokit).
* **BYOD**: Bring-Your-Own-Dataset (BYOD) to add additional datasets.

---

## <span class="sk-h2-span">Models</span>

__HeartKit__ provides a __model factory__ that allows you to easily create and train customized models. The model factory includes a number of modern networks well suited for efficient, real-time edge applications. Each model architecture exposes a number of high-level parameters that can be used to customize the network for a given application. These parameters can be set as part of the configuration accessible via the CLI and Python package.

- **[TCN](https://ambiqai.github.io/neuralspot-edge/models/tcn)**: A CNN leveraging dilated convolutions (key=`tcn`)
- **[U-Net](https://ambiqai.github.io/neuralspot-edge/models/unet)**: A CNN with encoder-decoder architecture for segmentation tasks (key=`unet`)
- **[U-NeXt](https://ambiqai.github.io/neuralspot-edge/models/unext)**: A U-Net variant leveraging MBConv blocks (key=`unext`)
- **[EfficientNetV2](https://ambiqai.github.io/neuralspot-edge/models/efficientnet)**: A CNN leveraging MBConv blocks (key=`efficientnet`)
- **[MobileOne](https://ambiqai.github.io/neuralspot-edge/models/mobileone)**: A CNN aimed at sub-1ms inference (key=`mobileone`)
- **[ResNet](https://ambiqai.github.io/neuralspot-edge/models/resnet)**: A popular CNN often used for vision tasks (key=`resnet`)
- **[Conformer](https://ambiqai.github.io/neuralspot-edge/models/conformer)**: A transformer composed of both convolutional and self-attention blocks (key=`conformer`)
- **[MetaFormer](https://ambiqai.github.io/neuralspot-edge/models/metaformer)**: A transformer composed of both spatial mixing and channel mixing blocks (key=`metaformer`)
- **[TSMixer](https://ambiqai.github.io/neuralspot-edge/models/tsmixer)**: An All-MLP Architecture for Time Series Classification (key=`tsmixer`)
- **[Bring-Your-Own-Model (BYOM)](https://ambiqai.github.io/heartkit/models/byom)**: Register new SoTA model architectures w/ custom configurations

---

## <span class="sk-h2-span">Model Zoo</span>

A number of pre-trained models are available for each task. These models are trained on a variety of datasets and are optimized for deployment on Ambiq's ultra-low power SoCs. In addition to providing links to download the models, __HeartKit__ provides the corresponding configuration files and performance metrics. The configuration files allow you to easily retrain the models or use them as a starting point for a custom model. Furthermore, the performance metrics provide insights into the model's accuracy, precision, recall, and F1 score. For a number of the models, we provide experimental and ablation studies to showcase the impact of various design choices. Check out the [Model Zoo](https://ambiqai.github.io/heartkit/zoo) to learn more about the available models and their corresponding performance metrics.

---

## <span class="sk-h2-span">Guides</span>

Checkout the [Guides](https://ambiqai.github.io/heartkit/guides) to see detailed examples and tutorials on how to use HeartKit for a variety of tasks. The guides provide step-by-step instructions on how to train, evaluate, and deploy models for a given task. In addition, the guides provide insights into the design choices and performance metrics for the models. The guides are designed to help you get up and running quickly and to provide a deeper understanding of the models and tasks available in HeartKit.

---
