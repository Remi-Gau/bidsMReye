"""Run coregistration and extract data."""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from bids import BIDSLayout
from deepmreye import preprocess

from bidsmreye.methods import methods
from bidsmreye.utils import check_layout
from bidsmreye.utils import Config
from bidsmreye.utils import config_to_dict
from bidsmreye.utils import copy_license
from bidsmreye.utils import create_bidsname
from bidsmreye.utils import create_dir_if_absent
from bidsmreye.utils import create_sidecar
from bidsmreye.utils import get_dataset_layout
from bidsmreye.utils import get_deepmreye_filename
from bidsmreye.utils import list_subjects
from bidsmreye.utils import move_file
from bidsmreye.utils import return_regex
from bidsmreye.utils import set_dataset_description
from bidsmreye.utils import write_dataset_description


log = logging.getLogger("bidsmreye")


def coregister_and_extract_data(img: str, non_linear_coreg: bool = False) -> None:
    """Coregister image to eye template and extract data from eye mask for one image.

    :param img: Image to coregister and extract data from
    :type img: str
    """
    (
        eyemask_small,
        eyemask_big,
        dme_template,
        mask,
        x_edges,
        y_edges,
        z_edges,
    ) = preprocess.get_masks()

    transforms = ["Affine", "Affine", "SyNAggro"] if non_linear_coreg else None

    preprocess.run_participant(
        img,
        dme_template,
        eyemask_big,
        eyemask_small,
        x_edges,
        y_edges,
        z_edges,
        transforms=transforms,
    )


def combine_data_with_empty_labels(layout_out: BIDSLayout, img: Path, i: int = 1) -> Path:
    """Combine data with empty labels.

    :param layout_out: _description_
    :type layout_out: _type_

    :param subject_label: _description_
    :type subject_label: _type_

    :param img: _description_
    :type img: _type_

    :param i: _description_, defaults to 1
    :type i: int, optional
    """
    log.info(f"Combining data with empty labels: {img}")

    # Load data and normalize it
    data = pickle.load(open(img, "rb"))
    data = preprocess.normalize_img(data)

    # If experiment has no labels use dummy labels
    # 10 is the number of subTRs used in the pretrained weights, 2 is XY
    labels = np.zeros((data.shape[3], 10, 2))

    entities = layout_out.parse_file_entities(img)

    # Store for each runs
    subj: dict[str, list[Any]] = {"data": [], "labels": [], "ids": []}
    subj["data"].append(data)
    subj["labels"].append(labels)
    subj["ids"].append(([entities["subject"]] * labels.shape[0], [i] * labels.shape[0]))

    output_file = create_bidsname(layout_out, Path(img), "no_label")

    preprocess.save_data(
        output_file.name,
        subj["data"],
        subj["labels"],
        subj["ids"],
        layout_out.root,
        center_labels=False,
    )

    file_to_move = Path(layout_out.root).joinpath("..", "bidsmreye", output_file.name)

    move_file(file_to_move, output_file)

    return output_file


def process_subject(
    cfg: Config, layout_in: BIDSLayout, layout_out: BIDSLayout, subject_label: str
) -> None:
    """Run coregistration and extract data for one subject.

    :param cfg: Configuration object.
    :type cfg: Config

    :param layout_in: Layout input dataset.
    :type layout_in: BIDSLayout

    :param layout_out: Layout output dataset.
    :type layout_out: BIDSLayout

    :param subject_label: Can be a regular expression.
    :type subject_label: str
    """
    log.info(f"Running subject: {subject_label}")

    this_filter = cfg.bids_filter["bold"]
    this_filter["suffix"] = return_regex(this_filter["suffix"])
    this_filter["task"] = return_regex(cfg.task)
    this_filter["space"] = return_regex(cfg.space)
    this_filter["subject"] = subject_label
    if cfg.run:
        this_filter["run"] = return_regex(cfg.run)

    log.debug(f"Looking for files with filter\n{this_filter}")

    bf = layout_in.get(
        return_type="filename",
        regex_search=True,
        **this_filter,
    )

    to_print = [str(Path(x).relative_to(layout_in.root)) for x in bf]
    log.debug(f"Found files\n{to_print}")

    for img in bf:

        log.info(f"Processing file: {Path(img).name}")

        coregister_and_extract_data(img, non_linear_coreg=cfg.non_linear_coreg)

        report_name = create_bidsname(layout_out, img, "report")
        deepmreye_mask_report = get_deepmreye_filename(layout_in, img, "report")
        move_file(deepmreye_mask_report, report_name)

        mask_name = create_bidsname(layout_out, img, "mask")
        deepmreye_mask_name = get_deepmreye_filename(layout_in, img, "mask")
        move_file(deepmreye_mask_name, mask_name)

        save_sampling_frequency_to_json(layout_out, img)

        combine_data_with_empty_labels(layout_out, mask_name)


def save_sampling_frequency_to_json(layout_out: BIDSLayout, img: str) -> None:
    func_img = nib.load(img)
    header = func_img.header
    repetition_time = header.get_zooms()[3]
    if repetition_time <= 1:
        log.warning(f"Found a repetition time of {repetition_time} seconds.")
    create_sidecar(layout_out, img, SamplingFrequency=1 / float(repetition_time))


def prepare_data(cfg: Config) -> None:
    """Run coregistration and extract data for all subjects.

    :param cfg: Configuration object
    :type cfg: Config
    """
    log.info("PREPARING DATA")

    layout_in = get_dataset_layout(cfg.input_folder, use_database=True)
    check_layout(cfg, layout_in)

    create_dir_if_absent(cfg.output_folder)
    layout_out = get_dataset_layout(cfg.output_folder)
    # TODO add readme and license
    layout_out = set_dataset_description(layout_out)
    layout_out.dataset_description["DatasetType"] = "derivative"
    layout_out.dataset_description["GeneratedBy"][0]["Name"] = "bidsmreye"
    layout_out.dataset_description["GeneratedBy"][0]["config"] = config_to_dict(cfg)
    write_dataset_description(layout_out)

    citation_file = methods(cfg.output_folder)
    log.info(f"Method section generated: {citation_file}")

    license_file = copy_license(cfg.output_folder)
    log.info(f"License file added: {license_file}")

    subjects = list_subjects(cfg, layout_in)

    if cfg.non_linear_coreg:
        log.debug("Using non-linear coregistration")

    for subject_label in subjects:

        process_subject(cfg, layout_in, layout_out, subject_label)
