
import os
import shutil

from metadata import load_h36m_metadata


if __name__ == '__main__':
    metadata = load_h36m_metadata()


    examples = [
        ('Eating', '1', '55011271'),
        ('Phoning', '2', '58860488'),
        ('WalkingDog', '2', '54138969'),
        ('Greeting', '2', '58860488'),
        ('Walking', '1', '54138969'),
        ('WalkingTogether', '1', '60457274'),
        ('Directions', '1','54138969')
    ]
    reverse = True
    flow_calcs = [
        ('open_cv', 25, 256, not reverse),
        ('flownet2', 1, 256, not reverse),
        ('flownet2', 5, 256, not reverse),
        ('flownet2', 25, 256, not reverse),
        ('flownet2', 25, 1024, reverse),
        ('flownet2', 5, 1024, reverse),
        ('pwc_net', 25, 1024, reverse)
    ]
    subject = 'S1'
    dataset_root = '/net/hci-storage01/groupfolders/compvis/hperrot/datasets/human3.6M'
    videos_dir = os.path.join(dataset_root, 'extracted', subject, 'Videos')

    selection_dir = '/export/home/hperrot/scratch/flow_viz'

    def find_key_by_value(search_dict, search_value):
        for k, v in search_dict.items():
            if search_dict[k] == search_value:
                return k
        raise KeyError

    for action, subaction, camera in examples:
        action_key = find_key_by_value(metadata.action_names, action)
        filename_src =  os.path.join(videos_dir, metadata.get_base_filename(subject, action_key, subaction, camera) + '.mp4')
        filename_dst = os.path.join(selection_dir, subject + '_' + action + '-' + subaction + '_' + camera, 'original.mp4' )
        # print('copy:', action, filename_src, filename_dst)
        os.makedirs(os.path.dirname(filename_dst), exist_ok=True)
        shutil.copyfile(filename_src, filename_dst)

        copied = 0
        for flow_calc_mode, flow_step, resolution, reverse in flow_calcs:
            filename_src = os.path.join(
                dataset_root,
                'visualized',
                'flow_' + flow_calc_mode,
                ('r_' if reverse else '') + str(flow_step) + '_' + str(resolution),
                subject,
                action + '-' + subaction + '_' + camera + '.mp4'
            )
            filename_dst = os.path.join(
                os.path.dirname(filename_dst),
                flow_calc_mode + ('_r_' if reverse else '_') + str(flow_step) + '_' + str(resolution) + '.mp4'
            )
            # print('copy:', action, filename_src, filename_dst)
            try:
                shutil.copyfile(filename_src, filename_dst)
                copied += 1
            except Exception as e:
                print('Error: ', e)

        print(str(copied), 'flow viedeos copied for', action + '-' + subaction + '_' + camera)
