import torch
import torch.nn as nn
import numpy as np
import time

class LSTMTrainer:
    def __init__(self, device='mps'):
        self.device = torch.device(device if torch.backends.mps.is_available() else 'cpu')
    
    def train(self, model, train_loader, val_loader, epochs=10, lr=0.001):
        model.to(self.device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        loss_fn = nn.CrossEntropyLoss()
        print(f"Training on {self.device}")
        
        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            start_time = time.time()
            
            for X, y in train_loader:
                X = X.to(self.device).float()
                y = y.to(self.device).long()
                optimizer.zero_grad()
                output, _ = model(X)
                loss = loss_fn(output, y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            avg_loss = train_loss / len(train_loader)
            elapsed = time.time() - start_time
            print(f"Epoch {epoch+1:2d}/{epochs} | Loss: {avg_loss:.4f} | Time: {elapsed:.2f}s")
        
        return model
    
    def predict(self, model, loader):
        model.eval()
        preds = []
        with torch.no_grad():
            for X, _ in loader:
                X = X.to(self.device).float()
                output, _ = model(X)
                preds.append(output.cpu().numpy())
        return np.concatenate(preds)
