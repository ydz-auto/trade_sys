"""
LSTM Strategy - LSTM 深度学习策略

使用 PyTorch LSTM 模型进行价格预测。
特征计算和模型推理都在 GPU 上完成，零拷贝。

用法：
    from domain.strategy.lstm_strategy import LSTMStrategy, LSTMConfig
    
    # 创建策略
    strategy = LSTMStrategy(LSTMConfig(
        input_size=21,  # 特征数量
        hidden_size=128,
        num_layers=2,
    ))
    
    # 训练
    await strategy.train(features_df, labels)
    
    # 预测
    signal = await strategy.predict(features_tensor)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from pathlib import Path
import asyncio
import numpy as np

from shared.acceleration import torch, device, is_gpu, to_gpu, to_cpu, clear_cache
from shared.progress import ProgressTracker, ProgressType, ProgressBar, get_progress_tracker
from infrastructure.logging import get_logger

logger = get_logger("lstm_strategy")


@dataclass
class LSTMConfig:
    """LSTM 配置"""
    input_size: int = 21
    hidden_size: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    bidirectional: bool = False
    
    sequence_length: int = 60
    prediction_horizon: int = 1
    
    learning_rate: float = 0.001
    batch_size: int = 64
    epochs: int = 100
    early_stopping_patience: int = 10
    
    threshold_up: float = 0.02
    threshold_down: float = -0.02
    
    model_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "bidirectional": self.bidirectional,
            "sequence_length": self.sequence_length,
            "prediction_horizon": self.prediction_horizon,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "threshold_up": self.threshold_up,
            "threshold_down": self.threshold_down,
        }


class LSTMModel(torch.nn.Module):
    """LSTM 模型"""
    
    def __init__(self, config: LSTMConfig):
        super().__init__()
        
        self.config = config
        
        self.lstm = torch.nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0,
            bidirectional=config.bidirectional,
        )
        
        lstm_output_size = config.hidden_size * (2 if config.bidirectional else 1)
        
        self.fc = torch.nn.Sequential(
            torch.nn.Linear(lstm_output_size, 64),
            torch.nn.ReLU(),
            torch.nn.Dropout(config.dropout),
            torch.nn.Linear(64, 32),
            torch.nn.ReLU(),
            torch.nn.Dropout(config.dropout),
            torch.nn.Linear(32, 1),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        前向传播
        
        Args:
            x: (batch, sequence_length, input_size)
        
        Returns:
            (batch, 1) 预测值
        """
        lstm_out, _ = self.lstm(x)
        
        last_output = lstm_out[:, -1, :]
        
        output = self.fc(last_output)
        
        return output


class LSTMStrategy:
    """
    LSTM 策略
    
    特点：
    1. 特征计算和模型推理都在 GPU 上
    2. 支持增量训练
    3. 自动保存/加载模型
    """
    
    def __init__(self, config: LSTMConfig):
        self.config = config
        self.model = LSTMModel(config).to(device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=config.learning_rate)
        self.criterion = torch.nn.MSELoss()
        
        self._is_trained = False
        self._feature_mean = None
        self._feature_std = None
        
        if config.model_path and Path(config.model_path).exists():
            self.load(config.model_path)
        
        logger.info(f"LSTM Strategy initialized on {device}")
    
    async def train(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        val_split: float = 0.2,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        训练模型
        
        Args:
            features: 特征 Tensor (N, input_size) 或 (N, sequence_length, input_size)
            labels: 标签 Tensor (N,) 或 (N, 1)
            val_split: 验证集比例
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            训练结果
        """
        self.model.train()
        
        if features.dim() == 2:
            features, labels = self._create_sequences(features, labels)
        
        if not isinstance(features, torch.Tensor):
            features = to_gpu(features)
        if not isinstance(labels, torch.Tensor):
            labels = to_gpu(labels)
        
        self._feature_mean = features.mean(dim=(0, 1), keepdim=True)
        self._feature_std = features.std(dim=(0, 1), keepdim=True) + 1e-8
        features = (features - self._feature_mean) / self._feature_std
        
        n = len(features)
        n_val = int(n * val_split)
        n_train = n - n_val
        
        train_features = features[:n_train]
        train_labels = labels[:n_train]
        val_features = features[n_train:]
        val_labels = labels[n_train:]
        
        train_dataset = torch.utils.data.TensorDataset(train_features, train_labels)
        train_loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )
        
        tracker = get_progress_tracker()
        task_id = tracker.create_task(
            ProgressType.LSTM_TRAIN,
            total=self.config.epochs,
            message="Training LSTM model",
            metadata={"batch_size": self.config.batch_size, "train_samples": n_train},
        )
        
        bar = ProgressBar(total=self.config.epochs, desc="LSTM Training")
        
        if progress_callback:
            progress_callback(0, self.config.epochs, "Starting training")
        
        best_val_loss = float('inf')
        patience_counter = 0
        train_losses = []
        val_losses = []
        
        for epoch in range(self.config.epochs):
            self.model.train()
            epoch_loss = 0.0
            
            for batch_features, batch_labels in train_loader:
                self.optimizer.zero_grad()
                
                outputs = self.model(batch_features)
                loss = self.criterion(outputs.squeeze(), batch_labels.squeeze())
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_train_loss = epoch_loss / len(train_loader)
            train_losses.append(avg_train_loss)
            
            val_loss = self._validate(val_features, val_labels)
            val_losses.append(val_loss)
            
            tracker.update(
                task_id,
                current=epoch + 1,
                message=f"Epoch {epoch+1}: loss={avg_train_loss:.4f}",
            )
            bar.update(1, message=f"loss={avg_train_loss:.4f}, val={val_loss:.4f}")
            
            if progress_callback:
                progress_callback(epoch + 1, self.config.epochs, f"loss={avg_train_loss:.4f}")
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{self.config.epochs}: train_loss={avg_train_loss:.6f}, val_loss={val_loss:.6f}")
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                if self.config.model_path:
                    self.save(self.config.model_path)
            else:
                patience_counter += 1
                if patience_counter >= self.config.early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    tracker.update(task_id, current=self.config.epochs, message=f"Early stopping at epoch {epoch+1}")
                    break
        
        self._is_trained = True
        
        tracker.complete(
            task_id,
            result={
                "epochs": len(train_losses),
                "final_train_loss": train_losses[-1],
                "final_val_loss": val_losses[-1],
                "best_val_loss": best_val_loss,
            },
            message=f"Training completed, best_val_loss={best_val_loss:.4f}",
        )
        
        return {
            "epochs": len(train_losses),
            "final_train_loss": train_losses[-1],
            "final_val_loss": val_losses[-1],
            "best_val_loss": best_val_loss,
        }
    
    def _validate(self, features: torch.Tensor, labels: torch.Tensor) -> float:
        """验证"""
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(features)
            loss = self.criterion(outputs.squeeze(), labels.squeeze())
        return loss.item()
    
    async def predict(self, features: torch.Tensor) -> int:
        """
        预测信号
        
        Args:
            features: 特征 Tensor (sequence_length, input_size) 或 (N, input_size)
        
        Returns:
            信号: 1 (买入), -1 (卖出), 0 (持有)
        """
        if not self._is_trained:
            logger.warning("Model not trained yet")
            return 0
        
        self.model.eval()
        
        if features.dim() == 2:
            if len(features) < self.config.sequence_length:
                return 0
            features = features[-self.config.sequence_length:].unsqueeze(0)
        elif features.dim() == 3:
            pass
        else:
            features = features.unsqueeze(0).unsqueeze(0)
        
        if not isinstance(features, torch.Tensor):
            features = to_gpu(features)
        
        if self._feature_mean is not None:
            features = (features - self._feature_mean) / self._feature_std
        
        with torch.no_grad():
            prediction = self.model(features).squeeze()
        
        pred_value = prediction.item()
        
        if pred_value > self.config.threshold_up:
            return 1
        elif pred_value < self.config.threshold_down:
            return -1
        return 0
    
    async def predict_batch(self, features: torch.Tensor) -> torch.Tensor:
        """
        批量预测
        
        Args:
            features: (batch, sequence_length, input_size)
        
        Returns:
            预测值 Tensor (batch,)
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained yet")
        
        self.model.eval()
        
        if self._feature_mean is not None:
            features = (features - self._feature_mean) / self._feature_std
        
        with torch.no_grad():
            predictions = self.model(features).squeeze()
        
        return predictions
    
    def _create_sequences(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        创建训练序列
        
        将 (N, input_size) 转换为 (N - sequence_length, sequence_length, input_size)
        """
        sequences = []
        sequence_labels = []
        
        for i in range(self.config.sequence_length, len(features) - self.config.prediction_horizon):
            seq = features[i - self.config.sequence_length:i]
            label = labels[i + self.config.prediction_horizon - 1]
            sequences.append(seq)
            sequence_labels.append(label)
        
        if sequences:
            return torch.stack(sequences), torch.stack(sequence_labels)
        return features.unsqueeze(0), labels
    
    def save(self, path: str):
        """保存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config.to_dict(),
            'feature_mean': self._feature_mean,
            'feature_std': self._feature_std,
            'is_trained': self._is_trained,
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str):
        """加载模型"""
        checkpoint = torch.load(path, map_location=device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self._feature_mean = checkpoint.get('feature_mean')
        self._feature_std = checkpoint.get('feature_std')
        self._is_trained = checkpoint.get('is_trained', True)
        logger.info(f"Model loaded from {path}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        
        return {
            "config": self.config.to_dict(),
            "total_params": total_params,
            "trainable_params": trainable_params,
            "is_trained": self._is_trained,
            "device": str(device),
        }


class LSTMStrategyBuilder:
    """LSTM 策略构建器"""
    
    @staticmethod
    def create_default(input_size: int = 21) -> LSTMStrategy:
        """创建默认配置的策略"""
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=128,
            num_layers=2,
            dropout=0.2,
            sequence_length=60,
            prediction_horizon=1,
        )
        return LSTMStrategy(config)
    
    @staticmethod
    def create_fast(input_size: int = 21) -> LSTMStrategy:
        """创建快速训练配置（适合快速实验）"""
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=64,
            num_layers=1,
            dropout=0.1,
            sequence_length=30,
            prediction_horizon=1,
            epochs=50,
            batch_size=128,
        )
        return LSTMStrategy(config)
    
    @staticmethod
    def create_deep(input_size: int = 21) -> LSTMStrategy:
        """创建深度配置（适合大数据集）"""
        config = LSTMConfig(
            input_size=input_size,
            hidden_size=256,
            num_layers=3,
            dropout=0.3,
            bidirectional=True,
            sequence_length=120,
            prediction_horizon=1,
            epochs=200,
            batch_size=32,
        )
        return LSTMStrategy(config)
