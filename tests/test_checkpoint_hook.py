import _path_setup  # noqa: F401

import shutil
from pathlib import Path
from copy import deepcopy

import torch
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from accelerate import Accelerator

from hurricore.trainers import Trainer
from hurricore.hooks import CheckpointHook


temp_folder_path = Path(__file__).parents[1] / '_temp_checkpoints'


class _TestTrainer(Trainer):
    def __init__(self):
        model = nn.Linear(1, 1)
        super().__init__(
            models=[model],
            optimizers=[AdamW(model.parameters(), lr=1e-3)],
            data_loaders=[DataLoader(range(10), batch_size=1, shuffle=True)],
            accelerator=Accelerator(),
            num_epochs=2,
        )
        self.hooks = [CheckpointHook(self, folder_path=temp_folder_path, interval=5)]
        self.iterated_results = []
    
    
    def training_step(self) -> torch.Tensor:
        batch = self.accelerator.gather(
            self.ctx.batches[0]
        ).sort()[0]
        self.iterated_results.append(batch)
        return torch.tensor(0.0)
    

def test_checkpoint_hook_dataloader():
    # set up test folder
    temp_folder_path.mkdir(parents=True, exist_ok=True)
    trainer = _TestTrainer()
    if trainer.accelerator.is_main_process:
        shutil.rmtree(temp_folder_path)
        temp_folder_path.mkdir(parents=True)
    trainer.accelerator.wait_for_everyone()
    
    trainer.run()
    assert len(trainer.iterated_results) == 20, "Not all batches are iterated."
    original_results = trainer.iterated_results.copy()
    
    # remove all but the 5th and the 15th
    if trainer.accelerator.is_main_process:
        ckpt_dirs = [d for d in temp_folder_path.iterdir() if d.is_dir() and d.name.startswith('ckpt_step_')]
        for ckpt_dir in ckpt_dirs:
            if ckpt_dir.name not in ['ckpt_step_5', 'ckpt_step_15']:
                shutil.rmtree(ckpt_dir)
    trainer.accelerator.wait_for_everyone()
    
    # test reproducibility on the 2nd epoch
    trainer = _TestTrainer()
    trainer.run()
    assert len(trainer.iterated_results) == 5, "Continued number of batches is not correct."
    new_results = trainer.iterated_results.copy()
    assert new_results == original_results[15:], "Continued batches do not match the original."

    # remove all but the 5th
    if trainer.accelerator.is_main_process:
        ckpt_dirs = [d for d in temp_folder_path.iterdir() if d.is_dir() and d.name.startswith('ckpt_step_')]
        for ckpt_dir in ckpt_dirs:
            if ckpt_dir.name not in ['ckpt_step_5']:
                shutil.rmtree(ckpt_dir)
    trainer.accelerator.wait_for_everyone()
    
    # test reproducibility on the 1st epoch
    trainer = _TestTrainer()
    trainer.run()
    assert len(trainer.iterated_results) == 15, "Continued number of batches is not correct."
    new_results = trainer.iterated_results.copy()
    assert new_results == original_results[5:], "Continued batches do not match the original."
    
    # clean up
    if trainer.accelerator.is_main_process:
        shutil.rmtree(temp_folder_path)
    trainer.accelerator.wait_for_everyone()
    

def test_checkpoint_hook_context():
    # set up test folder
    temp_folder_path.mkdir(parents=True, exist_ok=True)
    trainer = _TestTrainer()
    if trainer.accelerator.is_main_process:
        shutil.rmtree(temp_folder_path)
        temp_folder_path.mkdir(parents=True)
    trainer.accelerator.wait_for_everyone()
        
    trainer.run()
    original_context = deepcopy(trainer.ctx)
    
    # remove all but the 5th and the 15th
    if trainer.accelerator.is_main_process:
        ckpt_dirs = [d for d in temp_folder_path.iterdir() if d.is_dir() and d.name.startswith('ckpt_step_')]
        for ckpt_dir in ckpt_dirs:
            if ckpt_dir.name not in ['ckpt_step_5', 'ckpt_step_15']:
                shutil.rmtree(ckpt_dir)
    trainer.accelerator.wait_for_everyone()
    
    # test reproducibility on the 2nd epoch
    trainer = _TestTrainer()
    trainer.run()
    new_context = deepcopy(trainer.ctx)
    for key in vars(original_context).keys():
        new_value = getattr(new_context, key)
        original_value = getattr(original_context, key)
        assert new_value == original_value, \
            (
                f"Context key {key} does not match.\n"
                f"\tBefore: {original_value}\n"
                f"\tAfter: {new_value}\n"
            )

    # remove all but the 5th
    if trainer.accelerator.is_main_process:
        ckpt_dirs = [d for d in temp_folder_path.iterdir() if d.is_dir() and d.name.startswith('ckpt_step_')]
        for ckpt_dir in ckpt_dirs:
            if ckpt_dir.name not in ['ckpt_step_5']:
                shutil.rmtree(ckpt_dir)
    trainer.accelerator.wait_for_everyone()
    
    # test reproducibility on the 1st epoch
    trainer = _TestTrainer()
    trainer.run()
    new_context = deepcopy(trainer.ctx)
    for key in vars(original_context).keys():
        assert new_value == original_value, \
            (
                f"Context key {key} does not match.\n"
                f"\tBefore: {original_value}\n"
                f"\tAfter: {new_value}\n"
            )
    
    # clean up
    if trainer.accelerator.is_main_process:
        shutil.rmtree(temp_folder_path)
    trainer.accelerator.wait_for_everyone()
