import os
import logging
from pathlib import Path
from typing import List, Optional
import pydantic_argparse
from pydantic import BaseModel, Field
from .types import (
    EcgDownloadParams,
    EcgTrainParams,
    EcgTestParams,
    EcgDeployParams,
    EcgDemoParams,
)
from . import datasets as ds
from . import train
from . import evaluate
from . import demo
from . import deploy

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
logger = logging.getLogger("ECGARR")


class AppCommandArgments(BaseModel):
    """App command arguments as configuration file."""

    config_file: Optional[Path] = Field(None, description="Configuration JSON file")


class AppArguments(BaseModel):
    """App CLI arguments"""

    download_dataset: Optional[AppCommandArgments] = Field(description="Fetch dataset")
    train_model: Optional[AppCommandArgments] = Field(description="Train model")
    test_model: Optional[AppCommandArgments] = Field(description="Test model")
    deploy_model: Optional[AppCommandArgments] = Field(description="Deploy model")
    evb_demo: Optional[AppCommandArgments] = Field(description="EVB demo")


def download_dataset(command: AppCommandArgments):
    """Download dataset CLI command.
    Args:
        command (AppCommandArgments): Command arguments
    """
    params = EcgDownloadParams.parse_file(command.config_file)
    logger.info("#STARTED downloading dataset")
    ds.download_datasets(params=params)
    logger.info("#FINISHED downloading dataset")


def train_model(command: AppCommandArgments):
    """Train model CLI command.
    Args:
        command (AppCommandArgments): Command arguments
    """
    params = EcgTrainParams.parse_file(command.config_file)
    logger.info("#STARTED training model")
    train.train_model(params=params)
    logger.info("#FINISHED training model")


def test_model(command: AppCommandArgments):
    """Test model CLI command.
    Args:
        command (AppCommandArgments): Command arguments
    """

    params = EcgTestParams.parse_file(command.config_file)
    logger.info("#STARTED testing model")
    evaluate.evaluate_model(params=params)
    logger.info("#FINISHED testing model")


def deploy_model(command: AppCommandArgments):
    """Deploy model CLI command.
    Args:
        command (AppCommandArgments): Command arguments
    """
    params = EcgDeployParams.parse_file(command.config_file)
    logger.info("#STARTED deploying model")
    deploy.deploy_model(params=params)
    logger.info("#FINISHED deploying model")


def evb_demo(command: AppCommandArgments):
    """EVB Demo CLI command.
    Args:
        command (AppCommandArgments): Command arguments
    """
    params = EcgDemoParams.parse_file(command.config_file)
    logger.info("#STARTED evb demo")
    demo.evb_demo(params=params)
    logger.info("#FINISHED evb demo")


def run(inputs: Optional[List[str]] = None):
    """Main CLI app runner
    Args:
        inputs (Optional[List[str]], optional): App arguments. Defaults to CLI arguments.
    """
    parser = pydantic_argparse.ArgumentParser(
        model=AppArguments,
        prog="Heart arrhythmia Demo",
        description="Heart arrhythmia demo",
    )
    args = parser.parse_typed_args(inputs)

    if args.download_dataset:
        download_dataset(args.download_dataset)
    elif args.train_model:
        train_model(args.train_model)
    elif args.test_model:
        test_model(args.test_model)
    elif args.deploy_model:
        deploy_model(args.deploy_model)
    elif args.evb_demo:
        evb_demo(args.evb_demo)
    else:
        logger.error("Error: Unknown command")


if __name__ == "__main__":
    run()
