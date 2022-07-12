#!/usr/bin/env python3
"""foo."""
import argparse
import os
from glob import glob

from rich import print

from bidsmreye.prepare_data import prepare_data
from bidsmreye.utils import config


parser = argparse.ArgumentParser(description="Example BIDS App entrypoint script.")
parser.add_argument(
    "bids_dir",
    help="The directory with the input dataset "
    "formatted according to the BIDS standard.",
)
parser.add_argument(
    "output_dir",
    help="The directory where the output files "
    "should be stored. If you are running group level analysis "
    "this folder should be prepopulated with the results of the"
    "participant level analysis.",
)
parser.add_argument(
    "analysis_level",
    help="Level of the analysis that will be performed. "
    "Multiple participant level analyses can be run independently "
    "(in parallel) using the same output_dir.",
    choices=["participant"],
)
parser.add_argument(
    "--participant_label",
    help="The label(s) of the participant(s) that should be analyzed. The label "
    "corresponds to sub-<participant_label> from the BIDS spec "
    '(so it does not include "sub-"). If this parameter is not '
    "provided all subjects should be analyzed. Multiple "
    "participants can be specified with a space separated list.",
    nargs="+",
)
parser.add_argument(
    "--action",
    help="what to do",
    choices=["prepare", "combine", "generalize", "confounds"],
)
parser.add_argument(
    "--task",
    help="task to process",
)
parser.add_argument(
    "--space",
    help="space to process",
)
parser.add_argument(
    "--model",
    help="model to use",
)
parser.add_argument(
    "--debug",
    help="true or false",
)

args = parser.parse_args()

subjects_to_analyze = []
# only for a subset of subjects
if args.participant_label:
    subjects_to_analyze = args.participant_label
# for all subjects
else:
    subject_dirs = glob(os.path.join(args.bids_dir, "sub-*"))
    subjects_to_analyze = [subject_dir.split("-")[-1] for subject_dir in subject_dirs]

cfg = config()

if args.analysis_level == "participant":

    cfg["input_folder"] = args.bids_dir
    cfg["output_folder"] = args.output_dir

    if args.task:
        cfg["task"] = args.task
    if args.task:
        cfg["space"] = args.space

    if args.action == "prepare":
        prepare_data(cfg)
