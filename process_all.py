#!/usr/bin/env python3

from os import path, makedirs, listdir
from shutil import move
# from spacepy import pycdf
import cdflib
import numpy as np
import h5py
from subprocess import call
from tempfile import TemporaryDirectory
from tqdm import tqdm

from metadata import load_h36m_metadata

# set general params
global path_base
global threshold
min_kp_move = 40 # 40
path_base = '/net/hci-storage01/groupfolders/compvis/hperrot/datasets/human3.6M'

metadata = load_h36m_metadata()

# Subjects to include when preprocessing
all_subjects = {
    'S1': 1,
    'S5': 5,
    'S6': 6,
    'S7': 7,
    'S8': 8,
    'S9': 9,
    'S11': 11,
}

# Sequences with known issues
blacklist = {
    ('S11', '2', '2', '54138969'),  # Video file is corrupted
}


# Rather than include every frame from every video, we can instead wait for the pose to change
# significantly before storing a new example.
def select_frame_indices_to_include(subject, poses_3d_univ):
    # To process every single frame, uncomment the following line:
    # return np.arange(0, len(poses_3d_univ))

    # Take every 64th frame for the protocol #2 test subjects
    # (see the "Compositional Human Pose Regression" paper)
    # todo: uncomment for official evaluation ??????
    # if subject == 'S9' or subject == 'S11':
    #     return np.arange(0, len(poses_3d_univ), 64)
    # todo

    # process all frames
    return np.arange(0, len(poses_3d_univ))

    # Take only frames where movement has occurred for the protocol #2 train subjects
    frame_indices = []
    prev_joints3d = None
    threshold = min_kp_move ** 2  # Skip frames until at least one joint has moved by 40mm
    for i, joints3d in enumerate(poses_3d_univ):
        if prev_joints3d is not None:
            max_move = ((joints3d - prev_joints3d) ** 2).sum(axis=-1).max()
            if max_move < threshold:
                continue
        prev_joints3d = joints3d
        frame_indices.append(i)
    return np.array(frame_indices)


def infer_camera_intrinsics(points2d, points3d):
    """Infer camera instrinsics from 2D<->3D point correspondences."""
    pose2d = points2d.reshape(-1, 2)
    pose3d = points3d.reshape(-1, 3)
    x3d = np.stack([pose3d[:, 0], pose3d[:, 2]], axis=-1)
    x2d = (pose2d[:, 0] * pose3d[:, 2])
    alpha_x, x_0 = list(np.linalg.lstsq(x3d, x2d, rcond=-1)[0].flatten())
    y3d = np.stack([pose3d[:, 1], pose3d[:, 2]], axis=-1)
    y2d = (pose2d[:, 1] * pose3d[:, 2])
    alpha_y, y_0 = list(np.linalg.lstsq(y3d, y2d, rcond=-1)[0].flatten())
    return np.array([alpha_x, x_0, alpha_y, y_0])


def process_view(out_dir, subject, action, subaction, camera):
    subj_dir = path.join(path_base, 'extracted', subject)

    base_filename = metadata.get_base_filename(subject, action, subaction, camera)

    # Load joint position annotations
    cdf = cdflib.CDF(path.join(subj_dir, 'Poses_D2_Positions', base_filename + '.cdf'))
    poses_2d = np.array(cdf['Pose'])
    poses_2d = poses_2d.reshape(poses_2d.shape[1], 32, 2)

    # with pycdf.CDF(path.join(subj_dir, 'Poses_D2_Positions', base_filename + '.cdf')) as cdf:
    #     poses_2d = np.array(cdf['Pose'])
    #     poses_2d = poses_2d.reshape(poses_2d.shape[1], 32, 2)
    # with pycdf.CDF(path.join(subj_dir, 'Poses_D3_Positions_mono_universal', base_filename + '.cdf')) as cdf:
    #     poses_3d_univ = np.array(cdf['Pose'])
    #     poses_3d_univ = poses_3d_univ.reshape(poses_3d_univ.shape[1], 32, 3)
    # with pycdf.CDF(path.join(subj_dir, 'Poses_D3_Positions_mono', base_filename + '.cdf')) as cdf:
    #     poses_3d = np.array(cdf['Pose'])
    #     poses_3d = poses_3d.reshape(poses_3d.shape[1], 32, 3)

    # Infer camera intrinsics
    # camera_int = infer_camera_intrinsics(poses_2d, poses_3d)
    # camera_int_univ = infer_camera_intrinsics(poses_2d, poses_3d_univ)

    frame_indices = select_frame_indices_to_include(subject, poses_2d) # poses_3d_univ
    frames = frame_indices + 1
    video_file = path.join(subj_dir, 'Videos', base_filename + '.mp4')
    frames_dir = path.join(out_dir, 'imageSequence', camera)
    makedirs(path.join(path_base, frames_dir), exist_ok=True)

    # Check to see whether the frame images have already been extracted previously
    existing_files = {f for f in listdir(path.join(path_base, frames_dir))}
    frames_are_extracted = True
    for i in frames:
        filename = 'img_%06d.jpg' % i
        if filename not in existing_files:
            frames_are_extracted = False
            break

    if not frames_are_extracted:
        with TemporaryDirectory() as tmp_dir:
            # Use ffmpeg to extract frames into a temporary directory
            call([
                'ffmpeg',
                '-nostats', '-loglevel', '0',
                '-i', video_file,
                '-qscale:v', '3',
                path.join(tmp_dir, 'img_%06d.jpg')
            ])

            # Move included frame images into the output directory
            for i in frames:
                filename = 'img_%06d.jpg' % i
                path_from = path.join(tmp_dir, filename)
                path_to = path.join(path_base, frames_dir, filename)
                move(
                    path_from,
                    path_to
                )

    frames_path = []
    for i in frames:
        filename = 'img_%06d.jpg' % i
        frames_path.append(np.string_(path.join(frames_dir, filename))) # only save sub-path as meta data

    return {
        'keypoints': poses_2d[frame_indices],
        # 'pose/3d-univ': poses_3d_univ[frame_indices],
        # 'pose/3d': poses_3d[frame_indices],
        # 'intrinsics/' + camera: camera_int,
        # 'intrinsics-univ/' + camera: camera_int_univ,
        'frame_path': frames_path,
        'frame': frames,
        'fid': frame_indices,
        # 'camera': np.full(frames.shape, int(camera)),
        'subject': np.full(frames.shape, int(all_subjects[subject])),
        'action': np.full(frames.shape, int(action)),
        'subaction': np.full(frames.shape, int(subaction)),
        'pid': frame_indices
    }


def process_subaction(subject, action, subaction, subfolder, datasets):

    # out_dir = path.join('processed/min_kp_move_{}_plusEval'.format(min_kp_move), subject, metadata.action_names[action] + '-' + subaction)
    out_dir = path.join('processed', subfolder, subject, metadata.action_names[action] + '-' + subaction)
    makedirs(out_dir, exist_ok=True)

    for camera in tqdm(metadata.camera_ids, ascii=True, leave=False):
        if (subject, action, subaction, camera) in blacklist:
            continue

        try:
            annots = process_view(out_dir, subject, action, subaction, camera)
        except:
            print('Error processing sequence, skipping: ', repr((subject, action, subaction, camera)))
            continue

        for k, v in annots.items():
            if k in datasets:
                datasets[k].append(v)
            else:
                datasets[k] = [v]

    if len(datasets) == 0:
        return



def process_all(mode='train'):
    sequence_mappings = metadata.sequence_mappings

    assert mode in ['train', 'eval', 'all']

    if mode == 'train':
        included_subjects = { k: v for k, v in list(all_subjects.items())[:-2]}
    elif mode == 'eval':
        included_subjects = { k: v for k, v in list(all_subjects.items())[-2:]}
    elif mode == 'all':
        included_subjects = all_subjects

    subactions = []

    for subject in included_subjects.keys():
        subactions += [
            (subject, action, subaction)
            for action, subaction in sequence_mappings[subject].keys()
            if int(action) > 1  # Exclude '_ALL'
        ]

    datasets = {}
    for subject, action, subaction in tqdm(subactions, ascii=True, leave=False):
        process_subaction(subject, action, subaction, mode, datasets)

    datasets = {k: np.concatenate(v) for k, v in datasets.items()}

    with h5py.File(path.join(path_base, 'processed', mode, 'annot.h5'), 'w') as f:
        for name, data in datasets.items():
            f.create_dataset(name, data=data)

if __name__ == '__main__':
    #process_all('train')
    #process_all('eval')
    process_all('all')
