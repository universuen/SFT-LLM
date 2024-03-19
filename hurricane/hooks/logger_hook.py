import time
from logging import Logger

from torch.cuda import memory_reserved

from hurricane.hooks.hook_base import HookBase
from hurricane.trainers.trainer import Trainer
from hurricane.utils import get_list_mean


class LoggerHook(HookBase):
    def __init__(
        self, 
        logger: Logger = None,
        interval: int = 1, 
    ) -> None:
        super().__init__()
        if logger is None:
            logger = Logger('default')
        self.logger = logger
        self.interval = interval
    
    def on_training_start(self, trainer: Trainer) -> None:
        trainer.logger = self.logger
        if trainer.accelerator.is_main_process:
            assert hasattr(trainer.ctx, 'epochs')
            self.num_batches = len(trainer.data_loader)
            self.epochs = trainer.ctx.epochs
    
    def on_epoch_start(self, trainer: Trainer) -> None:
        if trainer.accelerator.is_main_process:
            super().on_epoch_start(trainer)
            assert hasattr(trainer.ctx, 'epoch')
            self.losses_per_batch = []
            self.epoch = trainer.ctx.epoch
            self.logger.info(f'Epoch {self.epoch} started')
            self.start_time = time.time()
        
    def on_step_end(self, trainer: Trainer) -> None:
        step_loss = trainer.accelerator.gather(trainer.ctx.step_loss).detach().mean().item()
        if trainer.accelerator.is_main_process:
            self.losses_per_batch.append(step_loss)
            idx = trainer.ctx.batch_idx + 1
            num_batches = len(trainer.data_loader)
            if idx % self.interval == 0 or idx == num_batches:
                progress = (idx / num_batches)
                elapsed_time = time.time() - self.start_time
                remaining_time = (elapsed_time / idx) * (num_batches - idx)
                formatted_remaining_time = time.strftime('%H:%M:%S', time.gmtime(remaining_time))
                self.logger.info(
                    f"Epoch: {self.epoch}/{self.epochs} | "
                    f"Step: {idx}/{num_batches} | "
                    f"Loss: {step_loss:.5f} | "
                    f"Progress: {progress:.2%} | "
                    f"Time left: {formatted_remaining_time} | "
                    f"Current lr: {[i['lr'] for i in trainer.optimizer.param_groups]} | "
                    f"Memory used: {memory_reserved() / 1024 ** 3:.2f}GB"
                )

    def on_epoch_end(self, trainer: Trainer) -> None:
        if trainer.accelerator.is_main_process:
            avg_loss = get_list_mean(self.losses_per_batch)
            self.logger.info(f'Epoch {self.epoch} finished with average loss: {avg_loss}')
            
