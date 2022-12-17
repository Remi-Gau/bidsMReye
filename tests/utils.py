from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bidsmreye.quality_control import compute_displacement
from bidsmreye.quality_control import compute_robust_outliers


def bidsmreye_eyetrack():

    output_location = Path().resolve()
    output_location = output_location.joinpath("tests", "data", "bidsmreye")

    confounds_tsv = output_location.joinpath(
        "sub-01",
        "func",
        "sub-01_task-nback_space-MNI152NLin2009cAsym_desc-bidsmreye_eyetrack.tsv",
    )

    return confounds_tsv


def create_basic_data():
    data = {
        "eye1_x_coordinate": np.random.randn(400),
        "eye1_y_coordinate": np.random.randn(400),
    }
    return data


def create_data_with_outliers():

    data = create_basic_data()

    data["eye_timestamp"] = np.arange(400)

    eye1_x_coordinate = data["eye1_x_coordinate"]
    eye1_y_coordinate = data["eye1_y_coordinate"]

    data["eye1_x_coordinate"][200] = (
        eye1_x_coordinate.mean() + eye1_x_coordinate.std() * 4
    )
    data["eye1_y_coordinate"][200] = (
        eye1_y_coordinate.mean() - eye1_y_coordinate.std() * 5
    )
    data["eye1_x_coordinate"][50] = eye1_x_coordinate.mean() - eye1_x_coordinate.std() * 5
    data["eye1_y_coordinate"][50] = eye1_y_coordinate.mean() + eye1_y_coordinate.std() * 4

    return data


def create_confounds_tsv():

    confounds_tsv = bidsmreye_eyetrack()

    df = pd.DataFrame(create_data_with_outliers())

    df["eye1_x_outliers"] = compute_robust_outliers(df["eye1_x_coordinate"])
    df["eye1_y_outliers"] = compute_robust_outliers(df["eye1_y_coordinate"])
    df["displacement"] = compute_displacement(
        df["eye1_x_coordinate"], df["eye1_y_coordinate"]
    )
    df["displacement_outliers"] = compute_robust_outliers(df["displacement"])

    df.to_csv(confounds_tsv, sep="\t", index=False)
