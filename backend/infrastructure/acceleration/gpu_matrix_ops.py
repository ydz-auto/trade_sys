import logging
from typing import List, Optional

import numpy as np
from infrastructure.acceleration.device_manager import DeviceManager

logger = logging.getLogger(__name__)

_TORCH_AVAILABLE = False
_torch = None

try:
    import torch as _torch_mod
    _torch = _torch_mod
    _TORCH_AVAILABLE = True
except ImportError:
    pass


def _torch_nanmean(t, dim=None, keepdim=False):
    nan_mask = _torch.isnan(t)
    valid = (~nan_mask).float()
    total = valid.sum(dim=dim, keepdim=keepdim).clamp(min=1.0)
    filled = t.clone()
    filled[nan_mask] = 0.0
    return filled.sum(dim=dim, keepdim=keepdim) / total


def _torch_nanstd(t, dim=None, keepdim=False):
    mean = _torch_nanmean(t, dim=dim, keepdim=True)
    diff = t - mean
    diff[_torch.isnan(diff)] = 0.0
    nan_mask = _torch.isnan(t)
    valid = (~nan_mask).float()
    n = valid.sum(dim=dim, keepdim=keepdim).clamp(min=2.0)
    var = (diff ** 2).sum(dim=dim, keepdim=keepdim) / (n - 1)
    return _torch.sqrt(var.clamp(min=0))


class GPUMatrixOps:

    def __init__(self):
        device_info = DeviceManager.detect()
        self._gpu_available = device_info.is_gpu and _TORCH_AVAILABLE
        self._device = None
        if self._gpu_available:
            try:
                self._device = _torch.device(device_info.device_type)
            except Exception:
                self._gpu_available = False
                self._device = None

    def zscore(self, matrix: np.ndarray, axis: int = 0) -> np.ndarray:
        if self._gpu_available and self._device is not None:
            t = _torch.tensor(matrix, dtype=_torch.float32, device=self._device)
            mean = _torch_nanmean(t, dim=axis, keepdim=True)
            std = _torch_nanstd(t, dim=axis, keepdim=True)
            std = _torch.where(std == 0, _torch.ones_like(std), std)
            result = (t - mean) / std
            return result.cpu().numpy()
        mean = np.nanmean(matrix, axis=axis, keepdims=True)
        std = np.nanstd(matrix, axis=axis, keepdims=True)
        std = np.where(std == 0, 1.0, std)
        return (matrix - mean) / std

    def rolling_zscore(self, series: np.ndarray, window: int) -> np.ndarray:
        if self._gpu_available and self._device is not None:
            t = _torch.tensor(series, dtype=_torch.float32, device=self._device)
            n = t.shape[0]
            result = _torch.full((n,), float('nan'), dtype=_torch.float32, device=self._device)
            kernel = _torch.ones(1, 1, window, dtype=_torch.float32, device=self._device) / window
            x = t.unsqueeze(0).unsqueeze(0)
            rolling_mean = _torch.nn.functional.conv1d(x, kernel)
            rolling_mean_sq = _torch.nn.functional.conv1d(x ** 2, kernel)
            rolling_var = rolling_mean_sq - rolling_mean ** 2
            rolling_std = _torch.sqrt(_torch.clamp(rolling_var, min=0))
            rolling_std = _torch.where(rolling_std == 0, _torch.ones_like(rolling_std), rolling_std)
            valid_start = window - 1
            valid_x = t[valid_start:]
            result[valid_start:] = (valid_x - rolling_mean.squeeze()) / rolling_std.squeeze()
            return result.cpu().numpy()
        import pandas as pd
        s = pd.Series(series)
        rolling = s.rolling(window=window)
        mean = rolling.mean()
        std = rolling.std()
        std = std.replace(0, 1.0)
        result = (s - mean) / std
        return result.values

    def compute_ic(self, features: np.ndarray, returns: np.ndarray) -> np.ndarray:
        if self._gpu_available and self._device is not None:
            X = _torch.tensor(features, dtype=_torch.float32, device=self._device)
            y = _torch.tensor(returns, dtype=_torch.float32, device=self._device)
            X_mean = _torch_nanmean(X, dim=0)
            y_mean = _torch_nanmean(y)
            X_centered = X - X_mean
            y_centered = y - y_mean
            numerator = _torch_nanmean(X_centered * y_centered.unsqueeze(1), dim=0)
            X_std = _torch_nanstd(X, dim=0)
            y_std = _torch_nanstd(y)
            denominator = X_std * y_std
            denominator = _torch.where(denominator == 0, _torch.ones_like(denominator), denominator)
            ic = numerator / denominator
            return ic.cpu().numpy()
        X_mean = np.nanmean(features, axis=0)
        y_mean = np.nanmean(returns)
        X_centered = features - X_mean
        y_centered = returns - y_mean
        numerator = np.nanmean(X_centered * y_centered[:, np.newaxis], axis=0)
        X_std = np.nanstd(features, axis=0)
        y_std = np.nanstd(returns)
        denominator = X_std * y_std
        denominator = np.where(denominator == 0, 1.0, denominator)
        return numerator / denominator

    def compute_rank_ic(self, features: np.ndarray, returns: np.ndarray) -> np.ndarray:
        if self._gpu_available and self._device is not None:
            X = _torch.tensor(features, dtype=_torch.float32, device=self._device)
            y = _torch.tensor(returns, dtype=_torch.float32, device=self._device)
            X_ranks = self._rank_2d(X)
            y_ranks = self._rank_1d(y)
            X_mean = _torch_nanmean(X_ranks, dim=0)
            y_mean = _torch_nanmean(y_ranks)
            X_centered = X_ranks - X_mean
            y_centered = y_ranks - y_mean
            numerator = _torch_nanmean(X_centered * y_centered.unsqueeze(1), dim=0)
            X_std = _torch_nanstd(X_ranks, dim=0)
            y_std = _torch_nanstd(y_ranks)
            denominator = X_std * y_std
            denominator = _torch.where(denominator == 0, _torch.ones_like(denominator), denominator)
            rank_ic = numerator / denominator
            return rank_ic.cpu().numpy()
        from scipy.stats import spearmanr
        n_features = features.shape[1]
        rank_ic = np.empty(n_features)
        for f in range(n_features):
            valid = ~(np.isnan(features[:, f]) | np.isnan(returns))
            if valid.sum() < 2:
                rank_ic[f] = np.nan
            else:
                corr, _ = spearmanr(features[valid, f], returns[valid])
                rank_ic[f] = corr
        return rank_ic

    def _rank_1d(self, t):
        nan_mask = _torch.isnan(t)
        valid = ~nan_mask
        n_valid = valid.sum().item()
        ranks = _torch.full_like(t, float('nan'))
        if n_valid > 0:
            sorted_indices = _torch.argsort(t[valid])
            temp_ranks = _torch.empty(n_valid, dtype=t.dtype, device=t.device)
            temp_ranks[sorted_indices] = _torch.arange(1, n_valid + 1, dtype=t.dtype, device=t.device)
            ranks[valid] = temp_ranks
        return ranks

    def _rank_2d(self, t):
        nan_mask = _torch.isnan(t)
        n_rows, n_cols = t.shape
        ranks = _torch.full_like(t, float('nan'))
        for col in range(n_cols):
            col_valid = ~nan_mask[:, col]
            n_valid = col_valid.sum().item()
            if n_valid > 0:
                sorted_indices = _torch.argsort(t[:, col][col_valid])
                temp_ranks = _torch.empty(n_valid, dtype=t.dtype, device=t.device)
                temp_ranks[sorted_indices] = _torch.arange(1, n_valid + 1, dtype=t.dtype, device=t.device)
                ranks[col_valid, col] = temp_ranks
        return ranks

    def compute_correlation_matrix(self, matrix: np.ndarray) -> np.ndarray:
        if self._gpu_available and self._device is not None:
            t = _torch.tensor(matrix, dtype=_torch.float32, device=self._device)
            mean = _torch_nanmean(t, dim=0, keepdim=True)
            std = _torch_nanstd(t, dim=0, keepdim=True)
            std = _torch.where(std == 0, _torch.ones_like(std), std)
            normalized = (t - mean) / std
            normalized = _torch.where(_torch.isnan(normalized), _torch.zeros_like(normalized), normalized)
            n = t.shape[0]
            corr = (normalized.T @ normalized) / n
            corr = _torch.clamp(corr, min=-1.0, max=1.0)
            return corr.cpu().numpy()
        return np.corrcoef(matrix, rowvar=False)

    def compute_forward_returns(self, prices: np.ndarray, horizons: List[int]) -> np.ndarray:
        n = len(prices)
        n_horizons = len(horizons)
        if self._gpu_available and self._device is not None:
            t = _torch.tensor(prices, dtype=_torch.float32, device=self._device)
            result = _torch.full((n, n_horizons), float('nan'), dtype=_torch.float32, device=self._device)
            for h_idx, horizon in enumerate(horizons):
                if horizon < n:
                    result[:n - horizon, h_idx] = t[horizon:] / t[:n - horizon] - 1
            return result.cpu().numpy()
        result = np.full((n, n_horizons), np.nan)
        for h_idx, horizon in enumerate(horizons):
            if horizon < n:
                result[:n - horizon, h_idx] = prices[horizon:] / prices[:n - horizon] - 1
        return result
