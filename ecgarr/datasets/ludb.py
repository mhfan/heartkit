import functools
import logging
import os
import tempfile
import warnings
import zipfile
from multiprocessing import Pool
from typing import List, Optional, Tuple, Union

import h5py
import numpy as np
import numpy.typing as npt
import sklearn.model_selection
import sklearn.preprocessing
from tqdm import tqdm

from ..types import EcgTask
from ..utils import download_file
from .dataset import EcgDataset
from .types import PatientGenerator, SampleGenerator
from .utils import butter_bp_filter

logger = logging.getLogger(__name__)

LudbSymbolMap = {
    "o": 0,  # Other
    "p": 1,  # P Wave
    "N": 2,  # QRS complex
    "t": 3,  # T Wave
}
LudbLeadsMap = {
    "i": 0,
    "ii": 1,
    "iii": 2,
    "avr": 3,
    "avl": 4,
    "avf": 5,
    "v1": 6,
    "v2": 7,
    "v3": 8,
    "v4": 9,
    "v5": 10,
    "v6": 11,
}


class LudbDataset(EcgDataset):
    """LUDB dataset"""

    def __init__(
        self, ds_path: str, task: EcgTask = EcgTask.rhythm, frame_size: int = 1250
    ) -> None:
        super().__init__(os.path.join(ds_path, "ludb"), task, frame_size)

    @property
    def sampling_rate(self) -> int:
        """Sampling rate in Hz"""
        return 500

    @property
    def mean(self) -> float:
        """Dataset mean"""
        return 0

    @property
    def std(self) -> float:
        """Dataset st dev"""
        return 1

    @property
    def patient_ids(self) -> npt.ArrayLike:
        """Get dataset patient IDs

        Returns:
            npt.ArrayLike: patient IDs
        """
        return np.arange(1, 201)

    def get_train_patient_ids(self) -> npt.ArrayLike:
        """Get dataset training patient IDs

        Returns:
            npt.ArrayLike: patient IDs
        """
        return self.patient_ids[:180]

    def get_test_patient_ids(self) -> npt.ArrayLike:
        """Get dataset patient IDs reserved for testing only

        Returns:
            npt.ArrayLike: patient IDs
        """
        return self.patient_ids[180:]

    def task_data_generator(
        self,
        patient_generator: PatientGenerator,
        samples_per_patient: Union[int, List[int]] = 1,
    ) -> SampleGenerator:
        """Task-level data generator.

        Args:
            patient_generator (PatientGenerator): Patient data generator
            samples_per_patient (Union[int, List[int]], optional): # samples per patient. Defaults to 1.

        Returns:
            SampleGenerator: Sample data generator
        """
        if self.task == EcgTask.segmentation:
            return self.segmentation_generator(
                patient_generator=patient_generator,
                samples_per_patient=samples_per_patient,
            )
        raise NotImplementedError()

    def segmentation_generator(
        self,
        patient_generator: PatientGenerator,
        samples_per_patient: Union[int, List[int]] = 1,
    ) -> SampleGenerator:
        """Generate a stream of short signals and their corresponding segment labels.
        These short signals are uniformly sampled from the segments in patient data by placing a frame in a random location.

        Args:
            patient_generator (PatientGenerator): Patient Generator
            samples_per_patient (Union[int, List[int]], optional): # samples per patient. Defaults to 1.
        Returns:
            SampleGenerator: Sample generator
        Yields:
            Iterator[SampleGenerator]
        """
        # NOTE: Labels are not provided on first N and last M samples so we'll discard
        start_offset = 600
        stop_offset = 950
        for _, pt in patient_generator:
            # NOTE: [:] will load all data into RAM- ideal for small dataset
            data = pt["data"][:]
            segs = pt["segmentations"][:]
            labels = np.zeros_like(data)
            for seg_idx in range(segs.shape[0]):
                seg = segs[seg_idx]
                labels[seg[2] : seg[3] + 0, seg[0]] = seg[1]
            for _ in range(samples_per_patient):
                # Randomly pick an ECG lead
                lead_idx = np.random.randint(data.shape[1])
                # Randomly select frame center point
                frame_start = np.random.randint(
                    start_offset, data.shape[0] - self.frame_size - stop_offset
                )
                frame_end = frame_start + self.frame_size
                x = (
                    data[frame_start:frame_end, lead_idx]
                    .astype(np.float32)
                    .reshape((self.frame_size, 1))
                )
                y = labels[frame_start:frame_end, lead_idx].reshape(
                    (self.frame_size, 1)
                )
                yield x, y
            # END FOR
        # END FOR

    def uniform_patient_generator(
        self,
        patient_ids: npt.ArrayLike,
        repeat: bool = True,
        shuffle: bool = True,
    ) -> PatientGenerator:
        """Yield data for each patient in the array.

        Args:
            patient_ids (pt.ArrayLike): Array of patient ids
            repeat (bool, optional): Whether to repeat generator. Defaults to True.
            shuffle (bool, optional): Whether to shuffle patient ids.. Defaults to True.

        Returns:
            PatientGenerator: Patient generator

        Yields:
            Iterator[PatientGenerator]
        """
        patient_ids = np.copy(patient_ids)
        while True:
            if shuffle:
                np.random.shuffle(patient_ids)
            for patient_id in patient_ids:
                pt_key = f"p{patient_id:05d}"
                with h5py.File(
                    os.path.join(self.ds_path, f"{pt_key}.h5"), mode="r"
                ) as h5:
                    yield patient_id, h5
            # END FOR
            if not repeat:
                break
        # END WHILE

    def convert_pt_wfdb_to_hdf5(
        self, patient: int, src_path: str, dst_path: str, force: bool = False
    ) -> Tuple[npt.ArrayLike, npt.ArrayLike, npt.ArrayLike]:
        """Convert LUDB patient data from WFDB to more consumable HDF5 format.

        Args:
            patient (int): Patient id (1-based)
            src_path (str): Source path to WFDB folder
            dst_path (str): Destination path to store HDF5 file

        Returns:
            Tuple[npt.ArrayLike, npt.ArrayLike, npt.ArrayLike]: data, segments, and fiducials
        """
        import wfdb  # pylint: disable=import-outside-toplevel

        pt_id = f"p{patient:05d}"
        pt_src_path = os.path.join(src_path, f"{patient}")
        rec = wfdb.rdrecord(pt_src_path)
        data = np.zeros_like(rec.p_signal)
        segs = []
        fids = []
        for i, lead in enumerate(rec.sig_name):
            lead_id = LudbLeadsMap.get(lead)
            ann = wfdb.rdann(pt_src_path, extension=lead)
            seg_start = seg_stop = sym_id = None
            data[:, lead_id] = rec.p_signal[:, i]
            for j, symbol in enumerate(ann.symbol):
                # Start of segment
                if symbol == "(":
                    seg_start = ann.sample[j]
                    seg_stop = None
                # Fiducial / segment type
                elif symbol in LudbSymbolMap:
                    sym_id = LudbSymbolMap.get(symbol)
                    if seg_start is None:
                        seg_start = ann.sample[j]
                    fids.append([lead_id, sym_id, ann.sample[j]])
                # End of segment (start and symbol are never 0 but can be None)
                elif symbol == ")" and seg_start and sym_id:
                    seg_stop = ann.sample[j]
                    segs.append([lead_id, sym_id, seg_start, seg_stop])
                else:
                    seg_start = seg_stop = None
                    sym_id = None
            # END FOR
        # END FOR
        segs = np.array(segs)
        fids = np.array(fids)

        if dst_path:
            os.makedirs(dst_path, exist_ok=True)
            pt_dst_path = os.path.join(dst_path, f"{pt_id}.h5")
            with h5py.File(pt_dst_path, "w") as h5:
                h5.create_dataset("data", data=data, compression="gzip")
                h5.create_dataset("segmentations", data=segs, compression="gzip")
                h5.create_dataset("fiducials", data=fids, compression="gzip")
            # END WITH
        # END IF

        return data, segs, fids

    def normalize(
        self, array: npt.ArrayLike, local: bool = True, filter_enable: bool = False
    ) -> npt.ArrayLike:
        """Normalize an array using the mean and standard deviation calculated over the entire dataset.

        Args:
            array (npt.ArrayLike):  Numpy array to normalize
            inplace (bool, optional): Whether to perform the normalization steps in-place. Defaults to False.
            local (bool, optional): Local mean and std or global. Defaults to True.
            filter_enable (bool, optional): Enable band-pass filter. Defaults to False.

        Returns:
            npt.ArrayLike: Normalized array
        """
        if filter_enable:
            filt_array = butter_bp_filter(
                array, lowcut=0.5, highcut=40, sample_rate=self.sampling_rate, order=2
            )
        else:
            filt_array = np.copy(array)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            filt_array = sklearn.preprocessing.scale(
                filt_array, with_mean=True, with_std=True, copy=False
            )
        return filt_array

    def convert_dataset_zip_to_hdf5(
        self,
        zip_path: str,
        patient_ids: Optional[npt.ArrayLike] = None,
        force: bool = False,
        num_workers: Optional[int] = None,
    ):
        """Convert dataset into individial patient HDF5 files.

        Args:
            zip_path (str): Zip path
            patient_ids (Optional[npt.ArrayLike], optional): List of patient IDs to extract. Defaults to all.
            force (bool, optional): Whether to force re-download if destination exists. Defaults to False.
            num_workers (int, optional): # parallel workers. Defaults to os.cpu_count().
        """
        if not patient_ids:
            patient_ids = self.patient_ids

        subdir = "lobachevsky-university-electrocardiography-database-1.0.1"
        with Pool(
            processes=num_workers
        ) as pool, tempfile.TemporaryDirectory() as tmpdir, zipfile.ZipFile(
            zip_path, mode="r"
        ) as zp:
            ludb_dir = os.path.join(tmpdir, "ludb")
            zp.extractall(ludb_dir)
            f = functools.partial(
                self.convert_pt_wfdb_to_hdf5,
                src_path=os.path.join(ludb_dir, subdir, "data"),
                dst_path=self.ds_path,
                force=force,
            )
            _ = list(tqdm(pool.imap(f, patient_ids), total=len(patient_ids)))
        # END WITH

    def download(self, num_workers: Optional[int] = None, force: bool = False):
        """Download LUDB dataset

        Args:
            ds_path (str): Path to store dataset
            num_workers (Optional[int], optional): # parallel workers. Defaults to None.
            force (bool, optional): Force redownload. Defaults to False.
        """

        logger.info("Downloading LUDB dataset")
        ds_url = (
            "https://physionet.org/static/published-projects/ludb/"
            "lobachevsky-university-electrocardiography-database-1.0.1.zip"
        )
        ds_zip_path = os.path.join(self.ds_path, "ludb.zip")
        os.makedirs(self.ds_path, exist_ok=True)
        if os.path.exists(ds_zip_path) and not force:
            logger.warning(
                f"Zip file already exists. Please delete or set `force` flag to redownload. PATH={ds_zip_path}"
            )
        else:
            download_file(ds_url, ds_zip_path, progress=True)

        # 2. Extract and convert patient ECG data to H5 files
        logger.info("Generating LUDB patient data")
        self.convert_dataset_zip_to_hdf5(
            zip_path=ds_zip_path, force=force, num_workers=num_workers
        )
        logger.info("Finished LUDB patient data")
