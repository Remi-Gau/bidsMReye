"""TODO."""
import logging
import os
import re
import shutil
import warnings
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

from attrs import converters
from attrs import define
from attrs import field
from bids import BIDSLayout  # type: ignore

log = logging.getLogger("rich")


@define
class Config:
    """Set up config and check that all required fields are set."""

    input_folder: str = field(default=None, converter=Path)

    @input_folder.validator
    def _check_input_folder(self, attribute, value):
        if not value.is_dir:
            raise ValueError(f"Input_folder must be an existing directory:\n{value}.")

    output_folder: str = field(default=None, converter=Path)
    participant: Optional[Any] = field(kw_only=True, default=None)
    space: Optional[Any] = field(kw_only=True, default=None)
    task: Optional[Any] = field(kw_only=True, default=None)
    run: Optional[Any] = field(kw_only=True, default=None)
    model_weights_file: Union[str, Path] = field(kw_only=True, default=None)
    debug: Union[str, bool] = field(kw_only=True, default=False)
    has_GPU = False

    def __attrs_post_init__(self):
        """Check that output_folder exists and gets info from layout if not specified."""
        os.environ["CUDA_VISIBLE_DEVICES"] = "0" if self.has_GPU else ""

        self.debug = converters.default_if_none(default=False)
        self.debug = converters.to_bool(self.debug)

        self.output_folder = self.output_folder.joinpath("bidsmreye")
        if not self.output_folder:
            self.output_folder.mkdir(parents=True, exist_ok=True)

        #  TODO add option to reset DB
        database_path = self.input_folder.joinpath("pybids_db")

        layout_in = BIDSLayout(
            self.input_folder,
            validate=False,
            derivatives=False,
            database_path=database_path,
        )

        if not database_path.is_dir():
            layout_in.save(database_path)

        self.check_argument(attribute="participant", layout_in=layout_in)
        self.check_argument(attribute="task", layout_in=layout_in)
        self.check_argument(attribute="run", layout_in=layout_in)
        self.check_argument(attribute="space", layout_in=layout_in)

    def check_argument(self, attribute, layout_in: BIDSLayout):
        """Check an attribute value compared to a the input dataset content."""
        if attribute == "participant":
            value = layout_in.get_subjects()
        elif attribute == "task":
            value = layout_in.get_tasks()
        elif attribute in ["space", "run"]:
            value = layout_in.get(return_type="id", target=attribute, datatype="func")

        self.listify(attribute)

        # convert all run values to integers
        if attribute in ["run"]:
            for i, j in enumerate(value):
                value[i] = int(j)
            tmp = [int(j) for j in getattr(self, attribute)]
            setattr(self, attribute, tmp)

        # keep only values that are intersection of requested values
        # and those present in the dataset
        if getattr(self, attribute):
            if missing_values := list(set(getattr(self, attribute)) - set(value)):
                warnings.warn(
                    f"{attribute}(s) {missing_values} not found in {self.input_folder}"
                )
            value = list(set(getattr(self, attribute)) & set(value))

        setattr(self, attribute, value)

        # run can be empty if run entity is not used
        if attribute not in ["run"] and not getattr(self, attribute):
            raise RuntimeError(f"No {attribute} not found in {self.input_folder}")

        return self

    def listify(self, attribute):
        """Convert attribute to list if not already."""
        if getattr(self, attribute) and not isinstance(getattr(self, attribute), list):
            setattr(self, attribute, [getattr(self, attribute)])

        return self


def move_file(input: Path, output: Path) -> None:
    """Move or rename a file and create target directory if it does not exist.

    Should work even the source and target names are on different file systems.

    Args:
        input (Path): File to move.

        output (str): _description_
    """
    log.info(f"{input.resolve()} --> {output.resolve()}")
    create_dir_for_file(output)
    shutil.copy(input, output)
    input.unlink()


def create_dir_if_absent(output_path: Union[str, Path]) -> None:
    """Create a path if it does not exist.

    Args:
        output_path (Path): _description_
    """
    if isinstance(output_path, str):
        output_path = Path(output_path)
    if not output_path.is_dir():
        log.info(f"Creating dir: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)


def create_dir_for_file(file: Path) -> None:
    """Create the path to a file if it does not exist.

    Args:
        file (Path): _description_
    """
    output_path = file.resolve().parent
    create_dir_if_absent(output_path)

    # TODO refactor with create_dir_if_absent


def return_regex(value: Union[str, Optional[list]]) -> Optional[str]:
    """Return the regular expression for a string or a list of strings.

    Args:
        value (str, Optional[list]):

    Returns:
        Optional[str]:
    """
    if isinstance(value, str):
        if value[0] != "^":
            value = f"^{value}"
        if not value.endswith("$"):
            value = f"{value}$"

    if isinstance(value, list):
        new_value = ""
        for i in value:
            new_value = f"{new_value}{return_regex(i)}|"
        value = new_value[:-1]

    return value


def list_subjects(cfg: Config, layout: BIDSLayout) -> list:
    """List subject in a BIDS dataset for a given Config.

    Args:
        layout (BIDSLayout): BIDSLayout of the dataset

        cfg (Config): Config object

    Raises:
        Exception: _description_

    Returns:
        _type_: _description_
    """
    subjects = layout.get(return_type="id", target="subject", subject=cfg.participant)

    if subjects == [] or subjects is None:
        raise RuntimeError("No subject found")

    if cfg.debug:
        subjects = [subjects[0]]
        log.debug("Running first subject only.")

    log.info(f"processing subjects: {subjects}")

    return subjects


def get_deepmreye_filename(layout: BIDSLayout, img: str, filetype: str = None) -> Path:
    """_summary_.

    Args:
        layout (BIDSLayout): BIDSLayout of the dataset.

        img (str): _description_

        filetype (str): Any of the following: None, "mask", "report". Defautls to None.

    Raises:
        Exception: _description_

    Returns:
        str: _description_
    """
    if not img:
        raise ValueError("No file")

    if isinstance(img, (list)):
        img = img[0]

    bf = layout.get_file(img)
    filename = bf.filename

    filename = return_deepmreye_output_filename(filename, filetype)

    filefolder = Path(img).parent
    filefolder = filefolder.joinpath(filename)

    return Path(filefolder).resolve()


def return_deepmreye_output_filename(filename: str, filetype: str = None) -> str:
    """_summary_.

    Args:
        filename (str): _description_

        filetype (str): Any of the following: None, "mask", "report". Defaults to None.

    Returns:
        str: _description_
    """
    if filetype is None:
        pass
    elif filetype == "mask":
        filename = "mask_" + re.sub(r"\.nii.*", ".p", filename)
    elif filetype == "report":
        filename = "report_" + re.sub(r"\.nii.*", ".html", filename)

    return filename
