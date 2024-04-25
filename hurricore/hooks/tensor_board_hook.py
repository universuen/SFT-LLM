import time
from pathlib import Path
from threading import Thread

from torch.utils.tensorboard import SummaryWriter
from tensorboard import program

from hurricore.hooks import Hook, LoggerHook
from hurricore.trainers import Trainer
from hurricore.utils import DummyObject, auto_name


class TensorBoardHook(Hook):
    msg_queue = []
    
    def __init__(
        self, 
        trainer: Trainer,
        folder_path: Path = None,
        interval: int = 1,
        record_grad: bool = False,
    ) -> None:
        super().__init__(trainer)
        # check validity
        assert interval > 0, 'TensorBoard interval must be greater than 0.'
        assert folder_path is not None and folder_path.is_dir(), 'Invalid TensorBoard folder path.'
        # setup self
        self.interval = interval
        self.folder_path = folder_path
        self.record_grad = record_grad
        self.writer = SummaryWriter(log_dir=self.folder_path) if trainer.accelerator.is_main_process else DummyObject()
        self._activate_msg_queue()
    
    
    def on_training_start(self) -> None:
        if self.trainer.accelerator.is_main_process:
            tb = program.TensorBoard()
            tb.configure(argv=[None, '--logdir', str(self.folder_path.parent)])
            url = tb.launch()
            LoggerHook.msg_queue.append(('info', f"Tensorboard is launched at {url}"))
    
    
    def on_step_end(self) -> None:
        step = self.trainer.ctx.global_step 
        if (step + 1) % self.interval == 0:
            loss = self.trainer.accelerator.gather(self.trainer.ctx.step_loss).detach().mean().item()
            self.writer.add_scalar('Loss/Training', loss, step)
            self.writer.flush()
                 
                   
    def on_epoch_end(self) -> None:
        if self.record_grad:
            step = self.trainer.ctx.global_step
            models = self.trainer.originals.models
            for model_name, model in zip(auto_name(models), models):
                for layer_name, param in model.named_parameters():
                    if param.grad is not None:
                        self.writer.add_histogram(f"Parameters/{model_name}-{layer_name}", param, step)
                        self.writer.add_histogram(f"Gradients/{model_name}-{layer_name}", param.grad, step)
            self.writer.flush()


    def on_training_end(self) -> None:
        self.writer.close()
    
    
    def recover_from_checkpoint(self) -> None:
        self.writer.purge_step = self.trainer.ctx.global_step
        self.writer.close()
        

    def _activate_msg_queue(self):
        def listen_and_process(self):
            while True:
                if len(self.msg_queue) > 0:
                    try:
                        method, kwargs = self.msg_queue.pop(0)
                        getattr(self.writer, method)(**kwargs)
                    except Exception as e:
                        LoggerHook.msg_queue.append(('error', f'Error in TensorBoardHook: {e}'))
                else:
                    time.sleep(0.01)
        Thread(target=listen_and_process, args=(self, ), daemon=True).start()
